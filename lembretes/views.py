"""
The reminder central. Every visit resyncs the derived reminders first, so the list is never
stale even without the cron command having run — see ``lembretes.services.sync_reminders``.
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from accounts.models import Profile
from billing.gating import auto_reminders_enabled
from core.views import OwnerCreateView

from .forms import ReminderForm
from .models import Reminder
from .services import sync_reminders


class ReminderIndexView(LoginRequiredMixin, TemplateView):
    template_name = 'lembretes/index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        sync_reminders(user)
        now = timezone.now()

        pending = Reminder.objects.filter(user=user, status=Reminder.Status.PENDING).order_by('remind_at')
        context['due_now'] = pending.filter(remind_at__lte=now)
        context['upcoming'] = pending.filter(remind_at__gt=now)
        # A tela não promete o que o sistema não faz: e-mail é o único canal que despacha
        # (D-028). Se a pessoa escolheu outro no perfil, dizemos que está em preparo.
        context['channel'] = user.profile.get_notification_channel_display()
        context['channel_pending'] = user.profile.notification_channel != Profile.NotificationChannel.EMAIL
        context['auto_reminders_enabled'] = auto_reminders_enabled(user)
        return context


class ReminderCreateView(OwnerCreateView):
    model = Reminder
    form_class = ReminderForm
    template_name = 'lembretes/object_form.html'
    success_url = reverse_lazy('lembretes:index')
    success_message = 'Lembrete criado.'
    extra_context = {'page_kicker': 'Lembretes', 'page_title': 'Novo lembrete'}


class ReminderCompleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        reminder = get_object_or_404(Reminder, pk=pk, user=request.user)
        reminder.mark_done()
        messages.success(request, 'Lembrete concluído.')
        return redirect('lembretes:index')


class ReminderCancelView(LoginRequiredMixin, View):
    def post(self, request, pk):
        reminder = get_object_or_404(Reminder, pk=pk, user=request.user)
        reminder.mark_cancelled()
        messages.success(request, 'Lembrete cancelado.')
        return redirect('lembretes:index')
