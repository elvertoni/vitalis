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
from django.views.generic import CreateView, TemplateView, UpdateView

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
