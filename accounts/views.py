"""Authentication and account views. All class based, all on native Django auth."""

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, TemplateView, UpdateView, View

from core.ratelimit import get_client_ip, is_rate_limited
from .forms import (
    EmailAuthenticationForm,
    ProfileForm,
    SignupForm,
    StyledPasswordResetForm,
    StyledSetPasswordForm,
    UserForm,
)


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
                for a in Appointment.objects.filter(user=user)
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
                for e in Exam.objects.filter(user=user)
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
                    'total_entries': s.entries.count(),
                }
                for s in WorkoutSession.objects.filter(user=user).order_by('-date')[:50]
            ],
        }

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            json_data = json.dumps(dossier, indent=2, ensure_ascii=False)
            zf.writestr('prontuario_vitalis.json', json_data)

            for exam in Exam.objects.filter(user=user, attachment__isnull=False):
                try:
                    if exam.attachment and exam.attachment.storage.exists(exam.attachment.name):
                        ext = Path(exam.attachment.name).suffix or '.pdf'
                        clean_name = exam.name.replace('/', '_').replace('\\', '_')[:50]
                        with exam.attachment.open('rb') as f:
                            zf.writestr(f'laudos/{clean_name}{ext}', f.read())
                except Exception:
                    pass

        buf.seek(0)
        filename = f"vitalis_prontuario_{user.pk}_{today:%Y%m%d}.zip"
        return FileResponse(buf, as_attachment=True, filename=filename, content_type='application/zip')

