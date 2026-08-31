"""Landing page, dashboard and the generic owner-scoped CRUD bases."""

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect
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
        from nutricao.models import Diet, daily_totals
        from saude.models import Appointment, Exam, Medication
        from treino.models import WorkoutRoutine, WorkoutSession, week_bounds

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

        # ── Treino ────────────────────────────────────────────────────────
        monday, sunday = week_bounds(today)
        context['sessions_this_week'] = WorkoutSession.objects.filter(
            user=user, date__gte=monday, date__lte=sunday
        ).count()
        context['next_routine_day'] = (
            WorkoutRoutine.objects.filter(user=user, is_active=True)
            .prefetch_related('days')
            .first()
        )

        # ── Nutrição ──────────────────────────────────────────────────────
        context['active_diet'] = Diet.objects.filter(user=user, is_active=True).first()
        context['today_totals'] = daily_totals(user, today)
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
    """
    Deletes an owned record. Some models use ``on_delete=PROTECT`` on purpose — a piece of
    training or health history should not vanish just because someone deletes the exercise
    or the treatment it is filed under. Trying to delete one of those here fails safely,
    with a plain-language message, instead of a 500.
    """

    template_name = 'core/object_confirm_delete.html'
    success_message = 'Registro excluído.'
    protected_message = 'Não é possível excluir: há outros registros vinculados a este.'
    delete_warning = None  # texto opcional exibido na confirmação quando a exclusão arrasta histórico junto

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['delete_warning'] = self.delete_warning
        return context

    def form_valid(self, form):
        self.object = self.get_object()
        redirect_url = self.get_success_url()
        try:
            self.object.delete()
        except ProtectedError:
            messages.error(self.request, self.protected_message)
            fallback = self.object.get_absolute_url() if hasattr(self.object, 'get_absolute_url') else redirect_url
            return redirect(fallback)
        messages.success(self.request, self.success_message)
        return redirect(redirect_url)


class ChildCreateView(OwnerCreateView):
    """
    Creates a record that hangs off a parent the person already owns.

    A routine day belongs to a routine, a set belongs to a session entry — the parent id
    comes from the URL, never from the form. ``get_parent()`` re-fetches it scoped to
    ``request.user`` on every request, so posting a parent id that belongs to someone else
    404s before any data is touched, the same guarantee ``OwnerQuerySetMixin`` gives reads.

    Subclasses set ``parent_model``, ``parent_field`` (the FK name on the child model) and,
    if the URL kwarg is not ``parent_pk``, ``parent_url_kwarg``.
    """

    parent_model = None
    parent_field = None
    parent_url_kwarg = 'parent_pk'
    parent_context_name = 'parent'

    def get_parent(self):
        return get_object_or_404(
            self.parent_model, pk=self.kwargs[self.parent_url_kwarg], user=self.request.user
        )

    def dispatch(self, request, *args, **kwargs):
        self.parent = self.get_parent()
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context[self.parent_context_name] = self.parent
        return context

    def form_valid(self, form):
        setattr(form.instance, self.parent_field, self.parent)
        return super().form_valid(form)
