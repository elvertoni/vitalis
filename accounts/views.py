"""Authentication and account views. All class based, all on native Django auth."""

import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import redirect
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, FormView, TemplateView, UpdateView, View

from core.ratelimit import get_client_ip, is_rate_limited
from .forms import (
    AccountDeleteForm,
    EmailAuthenticationForm,
    ProfileForm,
    SignupForm,
    StyledPasswordResetForm,
    StyledSetPasswordForm,
    UserForm,
)

logger = logging.getLogger(__name__)

# Retenção das cópias de segurança (scripts/backup.sh, BACKUP_KEEP_DAYS). A tela de exclusão e o
# e-mail citam o prazo: apagar a conta não alcança o backup que já foi gerado.
BACKUP_RETENTION_DAYS = 30


class SignupView(CreateView):
    """Creates the account and logs the person straight in, landing on the dashboard."""

    form_class = SignupForm
    template_name = 'accounts/signup.html'
    success_url = reverse_lazy('core:dashboard')

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('core:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        ip = get_client_ip(request)
        if is_rate_limited(f'signup:{ip}', max_requests=5, window_seconds=3600):
            messages.error(
                request,
                'Limite de cadastros atingido para esta conexão. Aguarde antes de tentar novamente.',
            )
            return self.render_to_response(self.get_context_data(form=self.get_form()))
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        messages.success(self.request, 'Conta criada. Complete seu perfil quando quiser.')
        return response


class VitalisLoginView(LoginView):
    authentication_form = EmailAuthenticationForm
    template_name = 'accounts/login.html'
    redirect_authenticated_user = True

    def post(self, request, *args, **kwargs):
        ip = get_client_ip(request)
        if is_rate_limited(f'login:{ip}', max_requests=5, window_seconds=60):
            messages.error(
                request,
                'Muitas tentativas de acesso em sequência. Aguarde um minuto antes de tentar novamente.',
            )
            return self.render_to_response(self.get_context_data(form=self.get_form()))
        return super().post(request, *args, **kwargs)


class VitalisLogoutView(LogoutView):
    pass


class ProfileView(LoginRequiredMixin, TemplateView):
    """Read only summary of the account, with links to the edit forms."""

    template_name = 'accounts/profile.html'

    def get_context_data(self, **kwargs):
        from billing.models import current_subscription
        from nutricao.models import WeightLog

        context = super().get_context_data(**kwargs)
        context['subscription'] = current_subscription(self.request.user)
        # O peso não é campo do perfil: é a última linha do histórico de pesagens (D-047).
        context['latest_weight'] = (
            WeightLog.objects.filter(user=self.request.user).order_by('-date').first()
        )
        return context


class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    form_class = ProfileForm
    template_name = 'accounts/profile_form.html'
    success_url = reverse_lazy('accounts:profile')

    def get_object(self, queryset=None):
        # The signal guarantees the profile exists for every account.
        return self.request.user.profile

    def form_valid(self, form):
        messages.success(self.request, 'Perfil atualizado.')
        return super().form_valid(form)


class AccountUpdateView(LoginRequiredMixin, UpdateView):
    form_class = UserForm
    template_name = 'accounts/account_form.html'
    success_url = reverse_lazy('accounts:profile')

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, 'Dados da conta atualizados.')
        return super().form_valid(form)


class AccountDeleteView(LoginRequiredMixin, FormView):
    """
    LGPD, Art. 18: the person deletes the account and everything filed under it.

    ``user.delete()`` cascades through every owned model (D-021) and ``core.signals`` removes the
    files after commit. Two locks come first: the current password and a typed word, under a
    per-account attempt limit. A paid subscription billed on the gateway is cancelled before
    anything is deleted, and if that fails the account stays: deleting it would leave someone
    being charged with no account left to complain from. Superusers are refused here, because
    the admin and the WhatsApp pairing depend on them (D-067).
    """

    form_class = AccountDeleteForm
    template_name = 'accounts/account_delete.html'
    attempt_limit = 5
    attempt_window_seconds = 900

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        from billing.models import current_subscription

        context = super().get_context_data(**kwargs)
        subscription = current_subscription(self.request.user)
        context.update({
            'is_admin_account': self.request.user.is_superuser,
            'summary': _account_summary(self.request.user),
            'paid_subscription': subscription if subscription and subscription.plan.price > 0 else None,
            'backup_days': BACKUP_RETENTION_DAYS,
        })
        return context

    def post(self, request, *args, **kwargs):
        if request.user.is_superuser:
            messages.error(request, 'Conta de administrador não pode ser excluída por esta tela.')
            return redirect('accounts:delete_account')
        if is_rate_limited(
            f'delete_account:{request.user.pk}',
            max_requests=self.attempt_limit,
            window_seconds=self.attempt_window_seconds,
        ):
            messages.error(request, 'Muitas tentativas seguidas. Aguarde 15 minutos antes de tentar de novo.')
            return redirect('accounts:delete_account')
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        from billing.models import current_subscription
        from billing.services import GatewayError, GatewayNotConfigured, get_gateway

        user = self.request.user
        subscription = current_subscription(user)
        if subscription and subscription.gateway_subscription_id:
            try:
                get_gateway().cancel(subscription)
            except (GatewayNotConfigured, GatewayError) as error:
                logger.warning('Exclusão da conta %s interrompida: cobrança não cancelada (%s)', user.pk, error)
                messages.error(
                    self.request,
                    'Não conseguimos cancelar a cobrança recorrente da sua assinatura, por isso a conta '
                    'não foi excluída. Tente de novo em alguns minutos.',
                )
                return redirect('accounts:delete_account')

        email, name, account_id = user.email, user.get_short_name(), user.pk
        with transaction.atomic():
            user.delete()
        logout(self.request)
        logger.info('Conta %s excluída a pedido da própria pessoa', account_id)
        _send_deletion_notice(email, name)
        messages.success(self.request, 'Sua conta e todos os seus registros foram excluídos.')
        return redirect('core:landing')


def _account_summary(user):
    """What the deletion takes, grouped the way the person thinks about it — not by model."""
    from assistente.models import Conversation
    from lembretes.models import Reminder
    from nutricao.models import DailyLog, Diet, Food, WeightLog
    from saude.models import Appointment, Exam, Medication, Treatment
    from treino.models import WorkoutRoutine, WorkoutSession

    exams = Exam.objects.filter(user=user)
    with_report = exams.exclude(attachment='').exclude(attachment__isnull=True).count()
    return [
        {'label': 'Exames', 'count': exams.count(), 'detail': f'{with_report} com laudo anexado' if with_report else ''},
        {'label': 'Consultas e tratamentos', 'count': Appointment.objects.filter(user=user).count() + Treatment.objects.filter(user=user).count(), 'detail': ''},
        {'label': 'Medicamentos', 'count': Medication.objects.filter(user=user).count(), 'detail': ''},
        {'label': 'Fichas e sessões de treino', 'count': WorkoutRoutine.objects.filter(user=user).count() + WorkoutSession.objects.filter(user=user).count(), 'detail': ''},
        {'label': 'Dietas, alimentos e registros de refeição', 'count': Diet.objects.filter(user=user).count() + Food.objects.filter(user=user).count() + DailyLog.objects.filter(user=user).count(), 'detail': ''},
        {'label': 'Pesagens', 'count': WeightLog.objects.filter(user=user).count(), 'detail': ''},
        {'label': 'Lembretes', 'count': Reminder.objects.filter(user=user).count(), 'detail': ''},
        {'label': 'Conversas com o Vitalis AI', 'count': Conversation.objects.filter(user=user).count(), 'detail': ''},
    ]


def _send_deletion_notice(email, name):
    # A conta já foi apagada: falha de SMTP não pode virar erro na tela, só registro no log.
    context = {'name': name, 'deleted_at': timezone.localtime(), 'backup_days': BACKUP_RETENTION_DAYS}
    try:
        send_mail(
            subject='Sua conta no Vitalis foi excluída',
            message=render_to_string('accounts/account_deleted_email.txt', context),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
        )
    except Exception:
        logger.warning('Aviso de exclusão de conta não enviado', exc_info=True)


class VitalisPasswordResetView(PasswordResetView):
    form_class = StyledPasswordResetForm
    template_name = 'accounts/password_reset.html'
    email_template_name = 'accounts/password_reset_email.txt'
    subject_template_name = 'accounts/password_reset_subject.txt'
    success_url = reverse_lazy('accounts:password_reset_done')

    def post(self, request, *args, **kwargs):
        ip = get_client_ip(request)
        if is_rate_limited(f'password_reset:{ip}', max_requests=3, window_seconds=300):
            messages.error(
                request,
                'Muitas solicitações de recuperação de senha. Aguarde alguns minutos antes de tentar novamente.',
            )
            return self.render_to_response(self.get_context_data(form=self.get_form()))
        return super().post(request, *args, **kwargs)


class VitalisPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'accounts/password_reset_done.html'


class VitalisPasswordResetConfirmView(PasswordResetConfirmView):
    form_class = StyledSetPasswordForm
    template_name = 'accounts/password_reset_confirm.html'
    success_url = reverse_lazy('accounts:password_reset_complete')


class VitalisPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'accounts/password_reset_complete.html'


class ExportUserDataView(LoginRequiredMixin, View):
    """
    LGPD data portability: exports the user's complete clinical and fitness dossier
    as a ZIP archive containing a structured JSON and all attached exam PDFs.
    """

    def get(self, request, *args, **kwargs):
        import io
        import json
        import zipfile
        from pathlib import Path
        from django.http import FileResponse
        from django.utils import timezone
        from saude.models import (
            Appointment,
            ClinicalNote,
            Doctor,
            Exam,
            LabPanel,
            Medication,
            Treatment,
        )
        from django.db.models import Count
        from assistente.models import Conversation, Message
        from treino.models import WorkoutRoutine, WorkoutSession
        from nutricao.models import Food, Diet, DailyLog, WeightLog

        user = request.user
        today = timezone.localdate()

        dossier = {
            'export_date': timezone.now().isoformat(),
            'user': {
                'id': user.pk,
                'email': user.email,
                'full_name': user.full_name,
                'date_joined': user.date_joined.isoformat(),
                'profile': {
                    'birth_date': str(user.profile.birth_date) if user.profile.birth_date else None,
                    'sex': user.profile.sex,
                    'height_cm': user.profile.height_cm,
                    'target_weight_kg': float(user.profile.target_weight_kg) if user.profile.target_weight_kg else None,
                    'phone': user.profile.phone,
                    'notification_channel': user.profile.notification_channel,
                },
            },
            'doctors': [
                {
                    'name': d.name,
                    'specialty': d.specialty,
                    'phone': d.phone,
                    'email': d.email,
                    'clinic_name': d.clinic_name,
                    'notes': d.notes,
                }
                for d in Doctor.objects.filter(user=user)
            ],
            'treatments': [
                {
                    'name': t.name,
                    'description': t.description,
                    'status': t.status,
                    'start_date': str(t.start_date),
                    'end_date': str(t.end_date) if t.end_date else None,
                    'notes': t.notes,
                }
                for t in Treatment.objects.filter(user=user)
            ],
            'medications': [
                {
                    'name': m.name,
                    'dosage': m.dosage,
                    'frequency': m.frequency,
                    'start_date': str(m.start_date),
                    'end_date': str(m.end_date) if m.end_date else None,
                    'schedule_times': m.schedule_times,
                    'weekdays': m.weekdays,
                    'is_active': m.is_active,
                }
                for m in Medication.objects.filter(user=user)
            ],
            'appointments': [
                {
                    'doctor': str(a.doctor),
                    'date': str(a.date),
                    'reason': a.reason,
                    'next_return_date': str(a.next_return_date) if a.next_return_date else None,
                    'notes': a.notes,
                }
                for a in Appointment.objects.filter(user=user).select_related('doctor')
            ],
            'exams': [
                {
                    'name': e.name,
                    'doctor': str(e.doctor) if e.doctor else None,
                    'status': e.status,
                    'requested_date': str(e.requested_date),
                    'done_date': str(e.done_date) if e.done_date else None,
                    'result_summary': e.result_summary,
                    'has_attachment': bool(e.attachment),
                }
                for e in Exam.objects.filter(user=user).select_related('doctor')
            ],
            # Resultados de laboratório: o número medido e a faixa contra a qual ele foi
            # lido. Sem a faixa, o valor exportado não diz se estava dentro ou fora.
            'lab_panels': [
                {
                    'title': panel.title,
                    'exam': panel.exam.name if panel.exam else None,
                    'sample_kind': panel.sample_kind,
                    'method': panel.method,
                    'results': [
                        {
                            'name': r.name,
                            'unit': r.unit,
                            'value': float(r.value),
                            'previous_value': float(r.previous_value) if r.previous_value else None,
                            'previous_label': r.previous_label,
                            'reference_low': float(r.ref_low),
                            'reference_high': float(r.ref_high),
                            'status': r.status,
                            'note': r.note,
                        }
                        for r in panel.results.all()
                    ],
                }
                for panel in LabPanel.objects.filter(user=user).prefetch_related('results')
            ],
            'clinical_notes': [
                {
                    'kind': n.kind,
                    'severity': n.severity,
                    'title': n.title,
                    'body': n.body,
                }
                for n in ClinicalNote.objects.filter(user=user)
            ],
            'weight_logs': [
                {'date': str(w.date), 'weight_kg': float(w.weight_kg), 'notes': w.notes}
                for w in WeightLog.objects.filter(user=user).order_by('date')
            ],
            'diets': [
                {
                    'name': d.name,
                    'goal': d.goal,
                    'daily_calorie_target': d.daily_calorie_target,
                    'protein_target_g': d.protein_target_g,
                    'is_active': d.is_active,
                }
                for d in Diet.objects.filter(user=user)
            ],
            'workout_routines': [
                {'name': r.name, 'description': r.description, 'is_active': r.is_active}
                for r in WorkoutRoutine.objects.filter(user=user)
            ],
            'workout_sessions': [
                {
                    'date': str(s.date),
                    'morning_after': s.morning_after,
                    'notes': s.notes,
                    'total_entries': s.entry_count,
                }
                for s in WorkoutSession.objects.filter(user=user)
                .annotate(entry_count=Count('entries'))
                .order_by('-date')[:50]
            ],
            # O que a pessoa perguntou ao Vitalis AI e o que ouviu de volta também é dado dela.
            'assistant_conversations': [
                {
                    'title': conversation.title,
                    'created_at': conversation.created_at.isoformat(),
                    'messages': [
                        {
                            'role': message.role,
                            'content': message.content,
                            'attachment_name': message.attachment_name,
                            'created_at': message.created_at.isoformat(),
                        }
                        for message in conversation.messages.all()
                    ],
                }
                for conversation in Conversation.objects.filter(user=user).prefetch_related('messages')
            ],
        }

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            json_data = json.dumps(dossier, indent=2, ensure_ascii=False)
            zf.writestr('prontuario_vitalis.json', json_data)

            def add_file(field_file, arcname):
                # Um arquivo que sumiu do disco não derruba a exportação inteira, mas também
                # não some calado: fica registrado no log de quem cuida do servidor.
                try:
                    if field_file and field_file.storage.exists(field_file.name):
                        with field_file.open('rb') as f:
                            zf.writestr(arcname, f.read())
                except Exception:
                    logging.getLogger(__name__).warning(
                        'Arquivo %s ficou fora da exportação', field_file.name, exc_info=True
                    )

            def clean(name):
                return name.replace('/', '_').replace('\\', '_')[:50]

            # O pk no nome evita que dois exames com o mesmo título se sobrescrevam no zip.
            for exam in Exam.objects.filter(user=user, attachment__isnull=False):
                ext = Path(exam.attachment.name).suffix or '.pdf'
                add_file(exam.attachment, f'laudos/{exam.pk}-{clean(exam.name)}{ext}')

            for message in Message.objects.filter(user=user, attachment__isnull=False).exclude(attachment=''):
                ext = Path(message.attachment.name).suffix
                stem = clean(Path(message.attachment_name).stem) or 'anexo'
                add_file(message.attachment, f'assistente/{message.conversation_id}-{message.pk}-{stem}{ext}')

        buf.seek(0)
        filename = f"vitalis_prontuario_{user.pk}_{today:%Y%m%d}.zip"
        return FileResponse(buf, as_attachment=True, filename=filename, content_type='application/zip')

