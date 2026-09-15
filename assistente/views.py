import logging
from pathlib import Path

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from core.ratelimit import is_rate_limited
from core.validators import validate_attachment
from core.views import OwnerDeleteView

from .models import Conversation, Message
from .services import build_clinical_context, call_gemini_api

logger = logging.getLogger(__name__)

# Cada envio custa uma chamada ao Gemini carregando o prontuário inteiro. O teto por pessoa
# segura um clique repetido ou um script em laço antes que vire conta alta ou chave bloqueada.
SEND_LIMIT = 20
SEND_WINDOW_SECONDS = 600

# O tipo que vai ao Gemini sai da extensão já validada, nunca do Content-Type do navegador.
ATTACHMENT_MIME = {
    '.pdf': 'application/pdf',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png': 'image/png',
}


class ChatIndexView(LoginRequiredMixin, TemplateView):
    """Main interface for Vitalis AI Chat."""

    template_name = 'assistente/chat.html'
    start_new = False  # `nova/` abre a tela limpa; a conversa só nasce na primeira pergunta

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        conversations = Conversation.objects.filter(user=user)

        conversation_id = self.kwargs.get('pk')
        if conversation_id:
            active_conv = get_object_or_404(Conversation, pk=conversation_id, user=user)
        elif self.start_new:
            active_conv = None
        else:
            active_conv = conversations.first()

        chat_messages = list(active_conv.messages.all()) if active_conv else []
        context.update({
            'conversations': conversations,
            'active_conversation': active_conv,
            'chat_messages': chat_messages,
            'gemini_configured': bool(settings.GEMINI_API_KEY),
            'record_summary': _record_summary(user),
            'suggestions': [] if chat_messages else _suggestions(user),
        })
        return context


class SendMessageView(LoginRequiredMixin, View):
    """Handles sending a message (and optional file) to Gemini and returning response."""

    http_method_names = ['post']

    def post(self, request, *args, **kwargs):
        user = request.user
        text = request.POST.get('content', '').strip()
        conversation_id = request.POST.get('conversation_id', '')
        upload = request.FILES.get('attachment')

        if not text and not upload:
            return _error('Escreva uma pergunta ou anexe um arquivo.', 400)
        if conversation_id and not conversation_id.isdigit():
            return _error('Conversa inválida. Recarregue a página.', 400)
        if not settings.GEMINI_API_KEY:
            return _error('O Vitalis AI ainda não foi ligado neste servidor.', 503)
        if is_rate_limited(f'assistente:{user.pk}', max_requests=SEND_LIMIT, window_seconds=SEND_WINDOW_SECONDS):
            return _error('Muitas perguntas em pouco tempo. Espere alguns minutos e tente de novo.', 429)

        attachment_bytes = None
        attachment_mime = None
        if upload:
            try:
                validate_attachment(upload)
            except ValidationError as error:
                return _error(error.messages[0], 400)
            attachment_bytes = upload.read()
            attachment_mime = ATTACHMENT_MIME[Path(upload.name).suffix.lower()]

        created = False
        if conversation_id:
            conversation = get_object_or_404(Conversation, pk=conversation_id, user=user)
        else:
            conversation = Conversation.objects.create(user=user, title=_title_from(text))
            created = True

        user_msg = Message.objects.create(
            user=user,
            conversation=conversation,
            role=Message.Role.USER,
            content=text or f'Analise o documento anexo: {upload.name}',
            attachment=upload,
            attachment_name=upload.name if upload else '',
        )

        if conversation.title == 'Nova conversa' and text:
            conversation.title = _title_from(text)
            conversation.save(update_fields=['title'])

        history = [{'role': m.role, 'content': m.content} for m in conversation.messages.all()]
        try:
            reply_text = call_gemini_api(
                api_key=settings.GEMINI_API_KEY,
                messages_history=history,
                system_instruction=build_clinical_context(user),
                attachment_bytes=attachment_bytes,
                attachment_mime=attachment_mime,
            )
        except Exception:
            # A pergunta sem resposta não fica no histórico: ela voltaria ao Gemini na próxima
            # chamada como contexto, e a pessoa veria uma conversa manca ao recarregar.
            logger.exception('Falha ao consultar o Gemini (conversa %s)', conversation.pk)
            user_msg.delete()  # o anexo sai do disco junto (core.signals)
            if created:
                conversation.delete()
            return _error('Não consegui falar com o Gemini agora. Sua pergunta não foi salva; tente de novo em instantes.', 502)

        assistant_msg = Message.objects.create(
            user=user,
            conversation=conversation,
            role=Message.Role.ASSISTANT,
            content=reply_text,
        )
        conversation.save()  # atualiza updated_at

        return JsonResponse({
            'status': 'ok',
            'conversation_id': conversation.pk,
            'conversation_url': conversation.get_absolute_url(),
            'user_message': {
                'id': user_msg.pk,
                'content': user_msg.content,
                'attachment_name': user_msg.attachment_name,
                'created_at': _clock(user_msg.created_at),
            },
            'assistant_message': {
                'id': assistant_msg.pk,
                'content': assistant_msg.content,
                'created_at': _clock(assistant_msg.created_at),
            },
        })


class DeleteConversationView(OwnerDeleteView):
    """Deletes a chat conversation; its messages and their files go with it (``core.signals``)."""

    model = Conversation
    success_url = reverse_lazy('assistente:index')
    success_message = 'Conversa excluída.'


def _error(message, status):
    return JsonResponse({'error': message}, status=status)


def _title_from(text):
    if not text:
        return 'Análise de documento'
    return text[:40] + ('...' if len(text) > 40 else '')


def _clock(moment):
    return timezone.localtime(moment).strftime('%H:%M')


def _record_summary(user):
    """What the assistant reads from the record, counted from the person's own rows."""
    from nutricao.models import Diet, WeightLog
    from saude.models import Exam, LabResult, Medication

    return {
        'weight': WeightLog.objects.filter(user=user).order_by('-date').first(),
        'diet': Diet.objects.filter(user=user, is_active=True).first(),
        'medications': Medication.objects.filter(user=user, is_active=True).count(),
        'exams': Exam.objects.filter(user=user).count(),
        'lab_results': LabResult.objects.filter(user=user).count(),
    }


def _suggestions(user):
    """
    Starter questions built from this person's data.

    They used to be literals naming one patient's lab value, diet and medicine, shown to every
    account (against D-041/D-061). Each one now appears only when the data behind it exists.
    """
    from nutricao.models import Diet
    from saude.models import LabResult, Medication

    suggestions = []

    flagged = (
        LabResult.objects.filter(user=user)
        .exclude(status=LabResult.Status.OK)
        .order_by('status', '-created_at')
        .first()
    )
    if flagged:
        suggestions.append({
            'icon': 'flask-conical',
            'title': f'Entender {flagged.name}',
            'prompt': f'O que fazer diante do resultado de {flagged.name} ({flagged.get_status_display().lower()}) no último exame?',
        })

    diet = Diet.objects.filter(user=user, is_active=True).first()
    if diet and diet.protein_target_g:
        limit = f' sem passar de {diet.daily_calorie_target} kcal' if diet.daily_calorie_target else ''
        suggestions.append({
            'icon': 'salad',
            'title': f'Bater {diet.protein_target_g} g de proteína',
            'prompt': f'Me dê opções práticas de lanche para bater {diet.protein_target_g} g de proteína{limit}.',
        })

    cycled = next(
        (m for m in Medication.objects.filter(user=user, is_active=True) if m.cycle_status),
        None,
    )
    if cycled:
        suggestions.append({
            'icon': 'pill',
            'title': f'Fases do {cycled.name}',
            'prompt': f'Como conduzir a fase atual do esquema do {cycled.name}?',
        })

    suggestions.append({
        'icon': 'glass-water',
        'title': 'Meta de água',
        'prompt': 'Calcule minha meta diária de água pelo peso atual e pelo treino.',
    })

    for fallback in (
        {
            'icon': 'file-text',
            'title': 'Ler um laudo',
            'prompt': 'Vou anexar um laudo. Explique os resultados e o que devo conversar com o médico.',
        },
        {
            'icon': 'dumbbell',
            'title': 'Revisar o treino',
            'prompt': 'Revise minha ficha de treino atual e sugira como progredir com segurança.',
        },
    ):
        if len(suggestions) >= 4:
            break
        suggestions.append(fallback)

    return suggestions[:4]
