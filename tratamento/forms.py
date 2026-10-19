"""Treatment forms. Styling comes from the Soluna widget classes shared with accounts."""

from datetime import datetime, timedelta
from decimal import Decimal

from django import forms
from django.db import transaction
from django.db.models import BLANK_CHOICE_DASH
from django.utils import timezone

from accounts.forms import TEXT_INPUT_CLASS, StyledFormMixin
from accounts.models import Profile
from nutricao.models import WeightLog
from saude.forms import DateInput
from saude.models import WEEKDAY_CHOICES, Medication

from .models import Injection, SideEffect, dose_text


class DateTimeInput(forms.DateTimeInput):
    input_type = 'datetime-local'

    def __init__(self, attrs=None):
        super().__init__(attrs={'class': TEXT_INPUT_CLASS, **(attrs or {})}, format='%Y-%m-%dT%H:%M')


class InjectionForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Injection
        fields = ['medication', 'applied_at', 'dose_mg', 'site', 'notes']
        widgets = {'applied_at': DateTimeInput()}

    def clean_applied_at(self):
        applied_at = self.cleaned_data['applied_at']
        # Registro é do que já aconteceu. Aplicação no futuro é quase sempre data errada
        # e faria a próxima dose sumir do card antes da hora.
        if applied_at > timezone.now() + timedelta(minutes=5):
            raise forms.ValidationError('A aplicação não pode estar no futuro.')
        return applied_at


class SideEffectForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = SideEffect
        fields = ['date', 'kind', 'intensity', 'injection', 'notes']
        widgets = {'date': DateInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # As aplicações mais recentes primeiro; o filtro por dono vem do OwnerFormMixin.
        self.fields['injection'].queryset = Injection.objects.select_related('medication').order_by('-applied_at')

    def clean_date(self):
        date = self.cleaned_data['date']
        if date > timezone.localdate():
            raise forms.ValidationError('A data não pode estar no futuro.')
        return date


class OnboardingForm(StyledFormMixin, forms.Form):
    """
    First access in one screen: body data, weight and, optionally, the injectable.

    Not a ModelForm because it writes four models at once (``Profile``, ``WeightLog``,
    ``saude.Medication`` and, if a shot was already given, ``Injection``). Each field maps
    to the column it fills; nothing here is stored twice.
    """

    # ── Sobre você ───────────────────────────────────────────────────────
    height_cm = forms.IntegerField(
        label='Altura (cm)', min_value=100, max_value=250,
        widget=forms.NumberInput(attrs={'placeholder': 'Ex.: 168', 'inputmode': 'numeric'}),
    )
    current_weight_kg = forms.DecimalField(
        label='Peso hoje (kg)', max_digits=5, decimal_places=2,
        min_value=Decimal('30'), max_value=Decimal('300'),
        widget=forms.NumberInput(attrs={'placeholder': 'Ex.: 92.5', 'step': '0.1', 'inputmode': 'decimal'}),
        help_text='Vira a primeira pesagem do histórico.',
    )
    target_weight_kg = forms.DecimalField(
        label='Peso-meta (kg)', required=False, max_digits=5, decimal_places=2,
        min_value=Decimal('30'), max_value=Decimal('300'),
        widget=forms.NumberInput(attrs={'placeholder': 'Ex.: 78', 'step': '0.1', 'inputmode': 'decimal'}),
        help_text='Opcional. Combine a meta com quem acompanha o seu tratamento.',
    )
    birth_date = forms.DateField(label='Data de nascimento', required=False, widget=DateInput())
    sex = forms.ChoiceField(label='Sexo', required=False, choices=BLANK_CHOICE_DASH + list(Profile.Sex.choices))

    # ── Seu tratamento ───────────────────────────────────────────────────
    medication_name = forms.CharField(
        label='Medicamento injetável', required=False, max_length=180,
        widget=forms.TextInput(attrs={'placeholder': 'Nome da caneta, como está na receita'}),
        help_text='Deixe em branco se não usa medicamento injetável.',
    )
    dose_mg = forms.DecimalField(
        label='Dose atual (mg)', required=False, max_digits=5, decimal_places=2,
        min_value=Decimal('0.01'),
        widget=forms.NumberInput(attrs={'placeholder': 'Ex.: 2.5', 'step': '0.01', 'inputmode': 'decimal'}),
    )
    weekday = forms.TypedChoiceField(
        label='Dia da aplicação', required=False, coerce=int, empty_value=None,
        choices=BLANK_CHOICE_DASH + WEEKDAY_CHOICES,
    )
    reminder_time = forms.TimeField(
        label='Horário do lembrete', required=False, initial='08:00',
        widget=forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'),
    )
    last_applied_on = forms.DateField(
        label='Última aplicação', required=False, widget=DateInput(),
        help_text='Opcional. Se já começou, a data da aplicação mais recente.',
    )
    last_site = forms.ChoiceField(
        label='Local da última aplicação', required=False,
        choices=BLANK_CHOICE_DASH + list(Injection.Site.choices),
    )

    ABOUT_FIELDS = ['height_cm', 'current_weight_kg', 'target_weight_kg', 'birth_date', 'sex']
    TREATMENT_FIELDS = ['medication_name', 'dose_mg', 'weekday', 'reminder_time', 'last_applied_on', 'last_site']

    def clean_last_applied_on(self):
        day = self.cleaned_data.get('last_applied_on')
        if day and day > timezone.localdate():
            raise forms.ValidationError('A data não pode estar no futuro.')
        return day

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('medication_name'):
            return cleaned
        # Com medicamento, dose e dia são o mínimo para a próxima aplicação existir.
        if cleaned.get('dose_mg') is None:
            self.add_error('dose_mg', 'Informe a dose para acompanhar a titulação.')
        if cleaned.get('weekday') is None:
            self.add_error('weekday', 'Escolha o dia da semana da aplicação.')
        if not cleaned.get('reminder_time'):
            self.add_error('reminder_time', 'Informe o horário para o lembrete sair.')
        return cleaned

    def sections(self):
        return [
            {'title': 'Sobre você', 'subtitle': 'Altura e peso são a base do IMC e do progresso até a meta.',
             'fields': [self[name] for name in self.ABOUT_FIELDS]},
            {'title': 'Seu tratamento', 'subtitle': 'Para lembrar o dia da aplicação e registrar a dose de cada semana.',
             'fields': [self[name] for name in self.TREATMENT_FIELDS]},
        ]

    @transaction.atomic
    def save(self, user):
        data = self.cleaned_data
        today = timezone.localdate()

        profile = user.profile
        profile.height_cm = data['height_cm']
        if data.get('target_weight_kg') is not None:
            profile.target_weight_kg = data['target_weight_kg']
        if data.get('birth_date'):
            profile.birth_date = data['birth_date']
        if data.get('sex'):
            profile.sex = data['sex']
        profile.save()

        # Uma pesagem por dia (constraint): refazer o onboarding hoje corrige a de hoje.
        WeightLog.objects.update_or_create(
            user=user, date=today, defaults={'weight_kg': data['current_weight_kg']},
        )

        medication = None
        if data.get('medication_name'):
            dose = data['dose_mg']
            # Refazer o primeiro acesso corrige o injetável que já existe: dois Medication com
            # o mesmo nome rendiam dois lembretes no dia da aplicação (D-073).
            medication = (
                Medication.objects.filter(user=user, is_injectable=True, name__iexact=data['medication_name'])
                .order_by('-created_at').first()
                or Medication(user=user, start_date=data.get('last_applied_on') or today)
            )
            medication.name = data['medication_name']
            medication.dosage = f'{dose_text(dose)} mg'
            medication.frequency = '1x por semana'
            medication.schedule_times = [data['reminder_time'].strftime('%H:%M')]
            medication.weekdays = [data['weekday']]
            medication.is_active = True
            medication.is_injectable = True
            medication.save()
            if data.get('last_applied_on'):
                site = data.get('last_site') or Injection.Site.ABDOMEN_LEFT
                # A mesma data enviada de novo é a mesma aplicação, não uma segunda.
                injection = medication.injections.filter(applied_at__date=data['last_applied_on']).first()
                if injection:
                    injection.dose_mg = dose
                    injection.site = site
                    injection.save()
                else:
                    applied_at = timezone.make_aware(
                        datetime.combine(data['last_applied_on'], data['reminder_time'])
                    )
                    Injection.objects.create(
                        user=user,
                        medication=medication,
                        applied_at=min(applied_at, timezone.now()),
                        dose_mg=dose,
                        site=site,
                    )
        return medication
