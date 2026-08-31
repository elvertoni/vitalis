"""Landing page, dashboard and the generic owner-scoped CRUD bases."""

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.utils import timezone
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
)

from .mixins import OwnerFormMixin, OwnerQuerySetMixin


class LandingView(TemplateView):
    """Sales page. Someone already logged in goes straight to the dashboard."""

    template_name = 'core/landing.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('core:dashboard')
        return super().dispatch(request, *args, **kwargs)


class DashboardView(LoginRequiredMixin, TemplateView):
    """
    Consolidated view of health, training and nutrition.

    The health panel is live; training and nutrition fill in with their own apps.
    """

    template_name = 'core/dashboard.html'

    def get_context_data(self, **kwargs):
        from saude.models import Appointment, Exam, Medication

        context = super().get_context_data(**kwargs)
        user = self.request.user
        today = timezone.localdate()
        horizon = today + timedelta(days=30)

        context['profile'] = user.profile
        context['upcoming_appointments'] = (
            Appointment.objects.filter(
                user=user, next_return_date__gte=today, next_return_date__lte=horizon
            )
            .select_related('doctor')
            .order_by('next_return_date')[:5]
        )
        context['upcoming_exams'] = (
            Exam.objects.filter(
                user=user,
                scheduled_date__gte=today,
                scheduled_date__lte=horizon,
                done_date__isnull=True,
            ).order_by('scheduled_date')[:5]
        )
        context['today_medications'] = [
            medication
            for medication in Medication.objects.filter(user=user, is_active=True)
            if medication.is_current_on(today)
        ][:6]

        # ── Lembretes das próximas 48h ───────────────────────────────────────
        #
        # Antecipa aqui o que a app `lembretes` da Sprint 5 vai formalizar num model
        # próprio: dose de hoje, exame marcado e retorno médico dentro da janela curta.
        soon = today + timedelta(days=2)
        reminders = []
        for medication in context['today_medications']:
            for time in medication.schedule_times:
                reminders.append({'title': medication.name, 'when': f'hoje, {time}', 'icon': 'pill'})
        for exam in Exam.objects.filter(
            user=user, scheduled_date__gte=today, scheduled_date__lte=soon, done_date__isnull=True
        ):
            reminders.append({'title': exam.name, 'when': exam.scheduled_date.strftime('%d/%m'), 'icon': 'flask-conical'})
        for appointment in Appointment.objects.filter(
            user=user, next_return_date__gte=today, next_return_date__lte=soon
        ).select_related('doctor'):
            reminders.append({
                'title': f'Retorno · {appointment.doctor}',
                'when': appointment.next_return_date.strftime('%d/%m'),
                'icon': 'calendar-clock',
            })
        context['reminders_48h'] = reminders[:8]
        return context


# ── Bases de CRUD com isolamento por dono ────────────────────────────────────
#
# Toda view de domínio herda de uma destas. Elas já trazem o login exigido, o filtro por
# dono e, nas de escrita, o carimbo do dono e o estreitamento dos campos relacionais.
# Uma view de domínio que não herde daqui está fora da camada de isolamento.


class OwnerListView(OwnerQuerySetMixin, ListView):
    paginate_by = 20


class OwnerDetailView(OwnerQuerySetMixin, DetailView):
    pass


class OwnerCreateView(LoginRequiredMixin, OwnerFormMixin, CreateView):
    """Creation needs no queryset filter: there is no object yet, only the owner stamp."""

    success_message = 'Registro criado.'

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, self.success_message)
        return response


class OwnerUpdateView(OwnerQuerySetMixin, OwnerFormMixin, UpdateView):
    success_message = 'Alterações salvas.'

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, self.success_message)
        return response


class OwnerDeleteView(OwnerQuerySetMixin, DeleteView):
    template_name = 'core/object_confirm_delete.html'
    success_message = 'Registro excluído.'

    def form_valid(self, form):
        messages.success(self.request, self.success_message)
        return super().form_valid(form)
