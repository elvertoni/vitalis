"""
Where a reminder turns into a message that leaves the system.

Two things live here on purpose. **What gets sent**: not every reminder is worth an
interruption. A dose of medicine and a meal of the diet are a routine the person already
lives — mailing eleven of those a day teaches them to ignore the channel, and the notice that
actually matters (something with no date booked yet) drowns. So only
``Reminder.Category.SCHEDULING`` leaves the building; everything else stays visible in the
central and on the dashboard. See ``DECISIONS.md`` D-044.

**How it is worded and delivered**: the channel is isolated in ``send_reminder`` so a second
one (WhatsApp through the Evolution API, which ``Profile.notification_channel`` has promised
since Sprint 5 — D-028) plugs in here, without the dispatcher command knowing about it.
"""

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse

from .models import Reminder

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


def send_reminder(reminder):
    """
    Delivers one reminder through the person's channel. E-mail is the only one implemented.

    ``Profile.notification_channel`` also accepts 'whatsapp' and 'push'; both fall back to
    e-mail here rather than failing silently, so nobody stops receiving a notice because of
    a setting the system cannot honour yet.
    """
    subject, body = build_message(reminder)
    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[reminder.user.email],
        fail_silently=False,
    )
