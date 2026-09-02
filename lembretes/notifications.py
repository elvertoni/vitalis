"""
Where a reminder turns into a message that leaves the system.

Two things live here on purpose. **What gets sent**: not every reminder is worth an
interruption. A dose of medicine and a meal of the diet are a routine the person already
lives — mailing eleven of those a day teaches them to ignore the channel, and the notice that
actually matters drowns. What leaves the building is decided per person and per category by
``ChannelPreference``; ``DEFAULT_CHANNELS`` below is what applies until someone chooses
otherwise. See ``DECISIONS.md`` D-044 and D-054.

**How it is worded and delivered**: the channel is isolated in ``send_reminder``. WhatsApp
goes through the Evolution API (``lembretes.whatsapp``) when the person picked it and the
gateway is configured; e-mail is the floor everything falls back to. The dispatcher command
knows none of this — it only decides *when* (D-045).
"""

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse

from accounts.models import Profile

from . import whatsapp
from .models import Reminder

logger = logging.getLogger(__name__)

EMAIL = 'email'
WHATSAPP = 'whatsapp'

# O padrão até a pessoa escolher. Só o que é *data a combinar com terceiro* sai sozinho:
# marcar o retorno enquanto há vaga, e a aproximação da consulta já marcada. Dose de remédio,
# refeição e treino são rotina que a pessoa já vive — ficam na central e no painel, e só saem
# por mensagem se ela pedir na tela de preferências (D-054).
DEFAULT_CHANNELS = {
    Reminder.Category.SCHEDULING: frozenset({EMAIL}),
    Reminder.Category.RETURN: frozenset({EMAIL}),
}
NO_CHANNEL = frozenset()

# Categorias oferecidas na tela de preferências, na ordem em que aparecem.
CONFIGURABLE_CATEGORIES = (
    Reminder.Category.SCHEDULING,
    Reminder.Category.RETURN,
    Reminder.Category.MEDICATION,
    Reminder.Category.EXAM,
    Reminder.Category.NUTRITION,
    Reminder.Category.TRAINING,
    Reminder.Category.OTHER,
)


def channels_for(user, category):
    """
    The channels one category may use for ``user``.

    An explicit ``ChannelPreference`` row wins; its absence means the person never touched
    this category, and the conservative default applies. Saving preferences therefore never
    mutes a category the product adds later.
    """
    from .models import ChannelPreference

    pref = ChannelPreference.objects.filter(user=user, category=category).first()
    if pref is None:
        return DEFAULT_CHANNELS.get(category, NO_CHANNEL)
    chosen = set()
    if pref.by_email:
        chosen.add(EMAIL)
    if pref.by_whatsapp:
        chosen.add(WHATSAPP)
    return frozenset(chosen)


def should_notify(reminder):
    """True when this reminder has at least one channel open for its owner."""
    return bool(channels_for(reminder.user, reminder.category))


def _absolute_url(reminder):
    """Link to the record that generated the reminder, or to the central as a fallback."""
    source = reminder.source
    path = (
        source.get_absolute_url()
        if source is not None and hasattr(source, 'get_absolute_url')
        else reverse('lembretes:index')
    )
    return f'{settings.SITE_URL}{path}'


def build_message(reminder):
    """The subject and body of one reminder. Plain text — same copy feeds any channel."""
    subject = f'Vitalis · {reminder.title}'
    lines = [reminder.title]
    if reminder.description:
        lines += ['', reminder.description]
    lines += ['', f'Abrir no Vitalis: {_absolute_url(reminder)}']
    return subject, '\n'.join(lines)


def _send_email(reminder):
    subject, body = build_message(reminder)
    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[reminder.user.email],
        fail_silently=False,
    )
    return 'email'


def _send_whatsapp(reminder):
    """Same copy as the e-mail, minus the subject line that a chat message has no use for."""
    _, body = build_message(reminder)
    whatsapp.send_text(reminder.user.profile.phone, body)
    return 'whatsapp'


def send_reminder(reminder):
    """
    Delivers one reminder and returns the channel that took it, or ``None``.

    The person chose, per category, which channels may carry it (``channels_for``). WhatsApp
    additionally needs the gateway configured and a phone on the profile; a failure talking to
    the gateway falls back to e-mail **only if e-mail was also chosen for that category** —
    silently mailing something deliberately kept off e-mail would undo the very choice the
    preferences screen exists to make.

    Returns ``None`` when nothing could be delivered, so the caller never marks as sent a
    reminder that did not leave.
    """
    allowed = channels_for(reminder.user, reminder.category)
    if not allowed:
        return None

    profile = reminder.user.profile
    if WHATSAPP in allowed and whatsapp.is_configured() and profile.phone:
        try:
            return _send_whatsapp(reminder)
        except whatsapp.WhatsAppError:
            logger.warning(
                'WhatsApp falhou para o lembrete %s; %s.',
                reminder.pk,
                'caindo para e-mail' if EMAIL in allowed else 'e-mail nao autorizado nesta categoria',
                exc_info=True,
            )

    if EMAIL in allowed:
        return _send_email(reminder)
    return None
