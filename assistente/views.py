import mimetypes
import os
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView

from .models import Conversation, Message
from .services import build_clinical_context, call_gemini_api


class ChatIndexView(LoginRequiredMixin, TemplateView):
    """Main interface for Vitalis AI Chat."""

    template_name = 'assistente/chat.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        conversations = Conversation.objects.filter(user=user)
        context['conversations'] = conversations

        conversation_id = self.kwargs.get('pk')
        if conversation_id:
            active_conv = get_object_or_404(Conversation, pk=conversation_id, user=user)
        else:
            active_conv = conversations.first()

        context['active_conversation'] = active_conv
        if active_conv:
            context['messages'] = active_conv.messages.all()
        else:
            context['messages'] = []

        # Ativação do Gemini
        api_key = getattr(settings, 'GEMINI_API_KEY', '') or os.environ.get('GEMINI_API_KEY', '')
        context['gemini_configured'] = bool(api_key)
        return context


class SendMessageView(LoginRequiredMixin, View):
    """Handles sending a message (and optional file) to Gemini and returning response."""

    def post(self, request, *args, **kwargs):
        user = request.user
        text = request.POST.get('content', '').strip()
        conversation_id = request.POST.get('conversation_id')
        attachment_file = request.FILES.get('attachment')

        if not text and not attachment_file:
            return JsonResponse({'error': 'Envie uma mensagem ou um anexo.'}, status=400)

        # 1. Recupera ou cria a conversa
        if conversation_id:
            conversation = get_object_or_404(Conversation, pk=conversation_id, user=user)
        else:
            title = text[:40] + ('...' if len(text) > 40 else '') if text else 'Análise de documento'
            conversation = Conversation.objects.create(user=user, title=title)

        # 2. Processa anexo se houver
        attachment_bytes = None
        attachment_mime = None
        attachment_name = ''
        if attachment_file:
            attachment_bytes = attachment_file.read()
            attachment_mime = attachment_file.content_type or mimetypes.guess_type(attachment_file.name)[0]
            attachment_name = attachment_file.name

        # 3. Salva a mensagem do usuário
        user_msg = Message.objects.create(
            user=user,
            conversation=conversation,
            role=Message.Role.USER,
            content=text or f"Analise o documento anexo: {attachment_name}",
            attachment=attachment_file,
            attachment_name=attachment_name,
        )

        # Atualiza título da conversa se for a primeira mensagem
        if conversation.title == 'Nova conversa' and text:
            conversation.title = text[:40] + ('...' if len(text) > 40 else '')
            conversation.save(update_fields=['title'])

        # 4. Constrói histórico e contexto clínico
        system_instruction = build_clinical_context(user)
        history = [
            {'role': m.role, 'content': m.content}
            for m in conversation.messages.all()
        ]

        # 5. Chama a API do Gemini
        api_key = getattr(settings, 'GEMINI_API_KEY', '') or os.environ.get('GEMINI_API_KEY', '')
        if not api_key:
            reply_text = (
                "⚠️ **Chave do Google AI Studio não configurada.**\n\n"
                "Para ativar o copiloto, configure a variável de ambiente `GEMINI_API_KEY` nas configurações do servidor."
            )
        else:
            try:
                reply_text = call_gemini_api(
                    api_key=api_key,
                    messages_history=history,
                    system_instruction=system_instruction,
                    attachment_bytes=attachment_bytes,
                    attachment_mime=attachment_mime,
                )
            except Exception as e:
                reply_text = f"❌ Ocorreu um erro ao consultar o assistente de inteligência: {str(e)}"

        # 6. Salva resposta da IA
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
            'user_message': {
                'id': user_msg.pk,
                'content': user_msg.content,
                'attachment_name': user_msg.attachment_name,
                'created_at': user_msg.created_at.strftime('%H:%M'),
            },
            'assistant_message': {
                'id': assistant_msg.pk,
                'content': assistant_msg.content,
                'created_at': assistant_msg.created_at.strftime('%H:%M'),
            },
        })


class NewConversationView(LoginRequiredMixin, View):
    """Starts a clean chat session."""

    def get(self, request, *args, **kwargs):
        conversation = Conversation.objects.create(user=request.user, title='Nova conversa')
        return redirect('assistente:conversation_detail', pk=conversation.pk)


class DeleteConversationView(LoginRequiredMixin, View):
    """Deletes a chat conversation."""

    def post(self, request, pk, *args, **kwargs):
        conv = get_object_or_404(Conversation, pk=pk, user=request.user)
        conv.delete()
        return redirect('assistente:index')
