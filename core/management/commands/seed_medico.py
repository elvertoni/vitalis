"""
Carrega um dossiê de saúde pessoal num usuário, de forma idempotente.

O comando é genérico e **não contém dado nenhum** — tudo vem de um JSON externo
(`--source`), que fica fora do git por ser dado sensível de saúde (ver DECISIONS.md D-041).
Rodar duas vezes com o mesmo arquivo não duplica: cada registro é casado por campo natural
(`update_or_create`).

Uso:

    python manage.py seed_medico --email pessoa@exemplo.com --source medico-data/seed.json \
        [--attachments-dir "C:\\caminho\\para\\os\\pdfs"]

A estrutura esperada do JSON está em `medico-seed.example.json` (na raiz do repo, sem dados).
"""

import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from nutricao.models import Diet, Food, Meal, MealItem, WeightLog
from saude.models import (
    Appointment,
    ClinicalNote,
    Doctor,
    Exam,
    LabPanel,
    LabResult,
    Medication,
    Treatment,
)

User = get_user_model()

MAX_ATTACHMENT_MB = 10


def _date(value):
    return datetime.strptime(value, '%Y-%m-%d').date() if value else None


def _time(value):
    return datetime.strptime(value, '%H:%M').time() if value else None


def _decimal(value):
    if value in (None, ''):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:  # pragma: no cover - erro de digitação no JSON
        raise CommandError(f'Valor decimal inválido: {value!r}') from exc


class Command(BaseCommand):
    help = 'Ingere um dossiê de saúde (JSON) num usuário, de forma idempotente.'

    def add_arguments(self, parser):
        parser.add_argument('--email', required=True, help='E-mail do usuário dono dos dados.')
        parser.add_argument('--source', required=True, help='Caminho do JSON com o dossiê.')
        parser.add_argument(
            '--attachments-dir',
            default=None,
            help='Pasta onde estão os PDFs referenciados em exams[].attachment_file.',
        )

    def handle(self, *args, **options):
        try:
            user = User.objects.get(email__iexact=options['email'])
        except User.DoesNotExist:
            raise CommandError(f'Nenhum usuário com e-mail {options["email"]}.')

        source = Path(options['source'])
        if not source.is_file():
            raise CommandError(f'Arquivo não encontrado: {source}')
        data = json.loads(source.read_text(encoding='utf-8'))

        attachments_dir = Path(options['attachments_dir']) if options['attachments_dir'] else None
        if attachments_dir and not attachments_dir.is_dir():
            raise CommandError(f'--attachments-dir não é uma pasta: {attachments_dir}')

        with transaction.atomic():
            self._profile(user, data.get('profile'))
            doctors = self._doctors(user, data.get('doctors', []))
            treatments = self._treatments(user, data.get('treatments', []), doctors)
            self._medications(user, data.get('medications', []), treatments)
            exams = self._exams(user, data.get('exams', []), doctors, treatments, attachments_dir)
            self._lab_panels(user, data.get('lab_panels', []), exams)
            self._clinical_notes(user, data.get('clinical_notes', []))
            self._appointments(user, data.get('appointments', []), doctors, treatments)
            foods = self._foods(user, data.get('foods', []))
            self._diets(user, data.get('diets', []), foods)
            self._weight_logs(user, data.get('weight_logs', []))

        self.stdout.write(self.style.SUCCESS('Ingestão concluída.'))

    # -- perfil --------------------------------------------------------------

    def _profile(self, user, payload):
        if not payload:
            return
        profile = user.profile
        for field in ('sex', 'notification_channel'):
            if payload.get(field):
                setattr(profile, field, payload[field])
        if payload.get('birth_date'):
            profile.birth_date = _date(payload['birth_date'])
        if payload.get('height_cm'):
            profile.height_cm = int(payload['height_cm'])
        if payload.get('target_weight_kg') is not None:
            profile.target_weight_kg = _decimal(payload['target_weight_kg'])
        if payload.get('phone'):
            profile.phone = payload['phone']
        profile.save()
        self.stdout.write('  perfil atualizado')

    # -- saúde --------------------------------------------------------------

    def _doctors(self, user, items):
        result = {}
        for item in items:
            doctor, _ = Doctor.objects.update_or_create(
                user=user,
                name=item['name'],
                defaults={
                    'specialty': item.get('specialty', ''),
                    'phone': item.get('phone', ''),
                    'email': item.get('email', ''),
                    'clinic_name': item.get('clinic_name', ''),
                    'clinic_address': item.get('clinic_address', ''),
                    'notes': item.get('notes', ''),
                },
            )
            result[item['name']] = doctor
        self.stdout.write(f'  {len(result)} médico(s)')
        return result

    def _treatments(self, user, items, doctors):
        result = {}
        for item in items:
            treatment, _ = Treatment.objects.update_or_create(
                user=user,
                name=item['name'],
                defaults={
                    'doctor': doctors.get(item.get('doctor')),
                    'description': item.get('description', ''),
                    'start_date': _date(item['start_date']),
                    'end_date': _date(item.get('end_date')),
                    'status': item.get('status', Treatment.Status.ONGOING),
                    'notes': item.get('notes', ''),
                },
            )
            result[item['name']] = treatment
        self.stdout.write(f'  {len(result)} tratamento(s)')
        return result

    def _medications(self, user, items, treatments):
        count = 0
        for item in items:
            Medication.objects.update_or_create(
                user=user,
                name=item['name'],
                start_date=_date(item['start_date']),
                defaults={
                    'treatment': treatments.get(item.get('treatment')),
                    'dosage': item.get('dosage', ''),
                    'frequency': item.get('frequency', ''),
                    'end_date': _date(item.get('end_date')),
                    'schedule_times': item.get('schedule_times', []),
                    'cycle_daily_days': item.get('cycle_daily_days'),
                    'cycle_alternates_after': item.get('cycle_alternates_after', False),
                    'is_active': item.get('is_active', True),
                },
            )
            count += 1
        self.stdout.write(f'  {count} medicamento(s)')

    def _exams(self, user, items, doctors, treatments, attachments_dir):
        count = attached = 0
        result = {}
        for item in items:
            exam, _ = Exam.objects.update_or_create(
                user=user,
                name=item['name'],
                requested_date=_date(item['requested_date']),
                defaults={
                    'doctor': doctors.get(item.get('doctor')),
                    'treatment': treatments.get(item.get('treatment')),
                    'scheduled_date': _date(item.get('scheduled_date')),
                    'done_date': _date(item.get('done_date')),
                    'result_summary': item.get('result_summary', ''),
                    'status': item.get('status', Exam.Status.REQUESTED),
                },
            )
            count += 1
            result[item['name']] = exam
            ref = item.get('attachment_file')
            if ref and attachments_dir and not exam.attachment:
                path = attachments_dir / ref
                if not path.is_file():
                    self.stderr.write(f'    anexo não encontrado, pulando: {ref}')
                    continue
                size_mb = path.stat().st_size / (1024 * 1024)
                if size_mb > MAX_ATTACHMENT_MB:
                    self.stderr.write(
                        f'    anexo {ref} tem {size_mb:.1f} MB (> {MAX_ATTACHMENT_MB} MB), pulando'
                    )
                    continue
                with path.open('rb') as fh:
                    exam.attachment.save(path.name, File(fh), save=True)
                attached += 1
        msg = f'  {count} exame(s)'
        if attachments_dir:
            msg += f', {attached} anexo(s)'
        self.stdout.write(msg)
        return result

    def _lab_panels(self, user, items, exams):
        """
        Painéis e resultados do laudo.

        Os resultados são recriados a cada rodada, como os itens de refeição: a chave
        natural de um resultado é o painel mais o nome, e reimportar o mesmo laudo com uma
        linha renomeada deixaria a antiga órfã na tela.
        """
        panels = results = 0
        for item in items:
            panel, _ = LabPanel.objects.update_or_create(
                user=user,
                title=item['title'],
                defaults={
                    'exam': exams.get(item.get('exam')),
                    'sample_kind': item.get('sample_kind', LabPanel.SampleKind.SERUM),
                    'sample_label': item.get('sample_label', ''),
                    'method': item.get('method', ''),
                    'order': item.get('order', 1),
                },
            )
            panels += 1
            panel.results.all().delete()
            for order, result in enumerate(item.get('results', []), start=1):
                LabResult.objects.create(
                    user=user,
                    panel=panel,
                    name=result['name'],
                    unit=result.get('unit', ''),
                    value=_decimal(result['value']),
                    previous_value=_decimal(result.get('previous_value')),
                    previous_label=result.get('previous_label', ''),
                    scale_min=_decimal(result['scale_min']),
                    scale_max=_decimal(result['scale_max']),
                    ref_low=_decimal(result['ref_low']),
                    ref_high=_decimal(result['ref_high']),
                    status=result.get('status', LabResult.Status.OK),
                    note=result.get('note', ''),
                    decimals=result.get('decimals', 1),
                    order=result.get('order', order),
                )
                results += 1
        self.stdout.write(f'  {panels} painel(is) laboratorial(is), {results} resultado(s)')

    def _clinical_notes(self, user, items):
        count = 0
        for item in items:
            ClinicalNote.objects.update_or_create(
                user=user,
                kind=item.get('kind', ClinicalNote.Kind.ALERT),
                title=item['title'],
                defaults={
                    'severity': item.get('severity', ClinicalNote.Severity.INFO),
                    'body': item['body'],
                    'icon': item.get('icon', ''),
                    'order': item.get('order', 1),
                },
            )
            count += 1
        self.stdout.write(f'  {count} nota(s) clínica(s)')

    def _appointments(self, user, items, doctors, treatments):
        count = 0
        for item in items:
            doctor = doctors.get(item['doctor'])
            if not doctor:
                raise CommandError(f'Consulta referencia médico inexistente: {item["doctor"]!r}')
            Appointment.objects.update_or_create(
                user=user,
                doctor=doctor,
                date=_date(item['date']),
                defaults={
                    'treatment': treatments.get(item.get('treatment')),
                    'reason': item.get('reason', ''),
                    'notes': item.get('notes', ''),
                    'next_return_date': _date(item.get('next_return_date')),
                },
            )
            count += 1
        self.stdout.write(f'  {count} consulta(s)')

    # -- nutrição ---------------------------------------------------------

    def _foods(self, user, items):
        result = {}
        for item in items:
            food, _ = Food.objects.update_or_create(
                user=user,
                name=item['name'],
                defaults={
                    'portion_base_g': int(item.get('portion_base_g', 100)),
                    'calories': _decimal(item['calories']),
                    'protein_g': _decimal(item.get('protein_g', 0)) or Decimal('0'),
                    'carbs_g': _decimal(item.get('carbs_g', 0)) or Decimal('0'),
                    'fat_g': _decimal(item.get('fat_g', 0)) or Decimal('0'),
                },
            )
            result[item['name']] = food
        self.stdout.write(f'  {len(result)} alimento(s)')
        return result

    def _diets(self, user, items, foods):
        for item in items:
            diet, _ = Diet.objects.update_or_create(
                user=user,
                name=item['name'],
                defaults={
                    'goal': item.get('goal', Diet.Goal.MAINTENANCE),
                    'daily_calorie_target': item.get('daily_calorie_target'),
                    'protein_target_g': item.get('protein_target_g'),
                    'carbs_target_g': item.get('carbs_target_g'),
                    'fat_target_g': item.get('fat_target_g'),
                    'is_active': item.get('is_active', True),
                },
            )
            for meal_data in item.get('meals', []):
                meal, _ = Meal.objects.update_or_create(
                    user=user,
                    diet=diet,
                    name=meal_data['name'],
                    defaults={
                        'time': _time(meal_data.get('time')),
                        'description': meal_data.get('description', ''),
                        'change_note': meal_data.get('change_note', ''),
                        'order': meal_data.get('order', 1),
                    },
                )
                # Itens são recriados a cada rodada — quantidade é a única coisa que muda e
                # não há chave natural boa para um item ("100 g de arroz" repetido).
                meal.items.all().delete()
                for item_data in meal_data.get('items', []):
                    food = foods.get(item_data['food'])
                    if not food:
                        raise CommandError(
                            f'Refeição {meal_data["name"]!r} usa alimento inexistente: '
                            f'{item_data["food"]!r}'
                        )
                    MealItem.objects.create(
                        user=user, meal=meal, food=food,
                        quantity_g=_decimal(item_data['quantity_g']),
                    )
        self.stdout.write(f'  {len(items)} dieta(s)')

    def _weight_logs(self, user, items):
        count = 0
        for item in items:
            WeightLog.objects.update_or_create(
                user=user,
                date=_date(item['date']),
                defaults={
                    'weight_kg': _decimal(item['weight_kg']),
                    'notes': item.get('notes', ''),
                },
            )
            count += 1
        self.stdout.write(f'  {count} registro(s) de peso')
