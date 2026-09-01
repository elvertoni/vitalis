"""
Where a reminder turns into a message that leaves the system.

Two things live here on purpose. **What gets sent**: not every reminder is worth an
interruption. A dose of medicine and a meal of the diet are a routine the person already
lives — mailing eleven of those a day teaches them to ignore the channel, and the notice that
actually matters (something with no date booked yet) drowns. So only
``Reminder.Category.SCHEDULING`` leaves the building; everything else stays visible in the
central and on the dashboard. See ``DECISIONS.md`` D-044.

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

# O único grupo que vira mensagem. Os outros continuam na tela, não na caixa de entrada.
NOTIFY_CATEGORIES = frozenset({Reminder.Category.SCHEDULING})


def should_notify(reminder):
    return reminder.category in NOTIFY_CATEGORIES


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
    Delivers one reminder and returns the channel that actually took it.

    WhatsApp only when the person asked for it, the gateway is configured and there is a
    phone on the profile. Anything short of that — and any failure talking to the gateway —
    falls back to e-mail: a notice that arrives on the wrong channel is worth much more than
    one that does not arrive. 'push' has no implementation and falls back the same way.
    """
    profile = reminder.user.profile
    wants_whatsapp = profile.notification_channel == Profile.NotificationChannel.WHATSAPP
    if wants_whatsapp and whatsapp.is_configured() and profile.phone:
        try:
            return _send_whatsapp(reminder)
        except whatsapp.WhatsAppError:
            logger.warning('WhatsApp falhou para o lembrete %s; caindo para e-mail.', reminder.pk, exc_info=True)
    return _send_email(reminder)
