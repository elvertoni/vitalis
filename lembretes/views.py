"""
The reminder central. Every visit resyncs the derived reminders first, so the list is never
stale even without the cron command having run — see ``lembretes.services.sync_reminders``.
"""

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from accounts.models import Profile
from billing.gating import auto_reminders_enabled
from core.views import OwnerCreateView

from . import whatsapp
from .forms import ReminderForm
from .models import ChannelPreference, Reminder
from .services import sync_reminders


def can_manage_whatsapp(user):
    """Apenas superusuários ou usuários com permissão explícita podem gerenciar a sessão global do WhatsApp."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if user.pk and user.has_perm('lembretes.manage_whatsapp'):
        return True
    return False


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
        context['channel_pending'] = (
            user.profile.notification_channel == Profile.NotificationChannel.WHATSAPP
            and not whatsapp.is_configured()
        ) or user.profile.notification_channel == Profile.NotificationChannel.PUSH
        context['can_manage_whatsapp'] = can_manage_whatsapp(user)
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


# ── Conexão do WhatsApp ──────────────────────────────────────────────────────
#
# A instância da Evolution API é o **remetente do sistema**, uma só para todas as contas —
# não o WhatsApp pessoal de cada pessoa. Conectar ou derrubar essa sessão tira (ou devolve)
# o canal de todo mundo, então é operação de quem administra a instalação, não do usuário
# comum, que controla apenas o próprio número e canal no perfil. Ver DECISIONS.md D-046.


class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """404 para quem não possui privilégio de gerência do WhatsApp — mesma escolha do isolamento por dono: não revelar a rota."""

    raise_exception = False

    def test_func(self):
        return can_manage_whatsapp(self.request.user)

    def handle_no_permission(self):
        from django.http import Http404

        if self.request.user.is_authenticated:
            raise Http404
        return super().handle_no_permission()


class WhatsAppPanelView(StaffRequiredMixin, TemplateView):
    """
    Painel de pareamento: mostra o estado da sessão e, se estiver fora, um QR novo.

    O QR é pedido a cada carregamento em vez de guardado: o gateway gera um código novo por
    chamada e cada um vive menos de um minuto — QR velho na tela é beco sem saída para quem
    está com o celular na mão.
    """

    template_name = 'lembretes/whatsapp.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['instance'] = settings.EVOLUTION_INSTANCE
        context['configured'] = whatsapp.is_configured()
        context['profile'] = self.request.user.profile
        if not context['configured']:
            return context
        try:
            state = whatsapp.connection_state()
            context['state'] = state
            if state == 'open':
                context['connected_number'] = whatsapp.connected_number()
            else:
                context['qr_base64'], context['pairing_code'] = whatsapp.connect()
        except whatsapp.WhatsAppError as exc:
            context['error'] = str(exc)
        return context


class WhatsAppStatusView(StaffRequiredMixin, View):
    """Só o estado, em JSON: a tela consulta em intervalos enquanto o QR está exposto."""

    def get(self, request):
        try:
            return JsonResponse({'state': whatsapp.connection_state()})
        except whatsapp.WhatsAppError as exc:
            return JsonResponse({'state': 'error', 'detail': str(exc)}, status=502)


class WhatsAppLogoutView(StaffRequiredMixin, View):
    def post(self, request):
        try:
            whatsapp.logout()
            messages.success(request, 'Sessão do WhatsApp encerrada. Nenhum lembrete sai por lá até parear de novo.')
        except whatsapp.WhatsAppError as exc:
            messages.error(request, f'Não foi possível encerrar a sessão: {exc}')
        return redirect('lembretes:whatsapp')


class WhatsAppTestView(StaffRequiredMixin, View):
    """Manda uma mensagem para o telefone do próprio perfil, para fechar o ciclo na hora."""

    def post(self, request):
        phone = request.user.profile.phone
        if not phone:
            messages.error(request, 'Preencha o telefone no seu perfil antes de testar.')
            return redirect('lembretes:whatsapp')
        try:
            whatsapp.send_text(phone, 'Vitalis conectado. É por aqui que seus avisos de agendamento vão chegar.')
            messages.success(request, f'Mensagem de teste enviada para {phone}.')
        except whatsapp.WhatsAppError as exc:
            messages.error(request, f'Falha no envio: {exc}')
        return redirect('lembretes:whatsapp')


class NotificationPreferenceView(LoginRequiredMixin, View):
    """
    Which categories may leave by e-mail and by WhatsApp, for this person.

    The screen writes one ``ChannelPreference`` row per configurable category on every save,
    including the ones left unticked. That is deliberate: a saved row means "the person
    decided", and only a decision should be able to silence a category — the absence of a row
    keeps meaning "never touched", so the conservative default still applies to whatever the
    product adds later (D-054).
    """

    template_name = 'lembretes/preferences.html'

    def _rows(self, user):
        from lembretes import notifications

        rows = []
        for category in notifications.CONFIGURABLE_CATEGORIES:
            channels = notifications.channels_for(user, category)
            rows.append({
                'value': category,
                'label': Reminder.Category(category).label,
                'help': CATEGORY_HELP.get(category, ''),
                'email': notifications.EMAIL in channels,
                'whatsapp': notifications.WHATSAPP in channels,
            })
        return rows

    def get(self, request):
        return TemplateResponse(request, self.template_name, self._context(request))

    def _context(self, request):
        from lembretes import notifications

        profile = request.user.profile
        return {
            'rows': self._rows(request.user),
            'whatsapp_ready': whatsapp.is_configured(),
            'has_phone': bool(profile.phone),
            'phone': profile.phone,
            'categories': notifications.CONFIGURABLE_CATEGORIES,
        }

    def post(self, request):
        from lembretes import notifications

        for category in notifications.CONFIGURABLE_CATEGORIES:
            ChannelPreference.objects.update_or_create(
                user=request.user, category=category,
                defaults={
                    'by_email': f'{category}_email' in request.POST,
                    'by_whatsapp': f'{category}_whatsapp' in request.POST,
                },
            )
        messages.success(request, 'Preferências de aviso salvas.')
        return redirect('lembretes:preferences')


# Uma linha por categoria explicando *quando* aquele aviso acontece, porque o nome sozinho
# ('Retorno médico') não diz se dispara uma vez ou todo dia — que é o que decide se a pessoa
# quer aquilo no WhatsApp.
CATEGORY_HELP = {
    Reminder.Category.SCHEDULING: 'Ligar para marcar algo que ainda não tem data: retorno pedido pelo médico, exame solicitado, tratamento sem acompanhamento agendado.',
    Reminder.Category.RETURN: 'Consulta já marcada se aproximando: 6, 4 e 2 dias antes, e na véspera.',
    Reminder.Category.MEDICATION: 'Cada horário de dose. Um remédio de uso contínuo dispara todos os dias.',
    Reminder.Category.EXAM: 'No dia do exame já agendado.',
    Reminder.Category.NUTRITION: 'Cada refeição da dieta, nos horários cadastrados. Vários por dia.',
    Reminder.Category.TRAINING: 'Avisos ligados ao treino. Hoje o sistema não gera nenhum automaticamente.',
    Reminder.Category.OTHER: 'Os lembretes que você cria à mão em “Novo lembrete”.',
}
