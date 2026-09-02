from django.db import models
from django.urls import reverse
from core.models import OwnedModel


class Conversation(OwnedModel):
    """A chat session between the user and Vitalis AI."""

    title = models.CharField('título', max_length=200, default='Nova conversa')
    created_at = models.DateTimeField('criada em', auto_now_add=True)
    updated_at = models.DateTimeField('atualizada em', auto_now=True)

    class Meta:
        verbose_name = 'conversa'
        verbose_name_plural = 'conversas'
        ordering = ['-updated_at']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('assistente:conversation_detail', args=[self.pk])


class Message(OwnedModel):
    """An individual message in a conversation with optional attachment."""

    class Role(models.TextChoices):
        USER = 'user', 'Usuário'
        ASSISTANT = 'assistant', 'Assistente'

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name='conversa',
    )
    role = models.CharField('papel', max_length=12, choices=Role.choices)
    content = models.TextField('conteúdo')
    attachment = models.FileField(
        'anexo',
        upload_to='assistente/%Y/%m/',
        null=True,
        blank=True,
        help_text='PDF ou imagem de exame, receita ou refeição.',
    )
    attachment_name = models.CharField('nome do anexo', max_length=255, blank=True)
    created_at = models.DateTimeField('enviada em', auto_now_add=True)

    class Meta:
        verbose_name = 'mensagem'
        verbose_name_plural = 'mensagens'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.get_role_display()}: {self.content[:40]}...'
