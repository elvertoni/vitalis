"""
The v1 dispatcher: run this via cron every few minutes.

Two steps, per active user: resync their derived reminders (so a medication added five
minutes ago is already covered), then e-mail whatever is pending and due. Channel is
e-mail only for v1, per PRD 9.3 — ``Profile.notification_channel`` accepts 'whatsapp' and
'push' already, so the UI doesn't lie about what is coming, but nothing dispatches through
them yet. See ``DECISIONS.md`` D-028.
"""

from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone

from lembretes.models import Reminder
from lembretes.services import sync_reminders

User = get_user_model()


class Command(BaseCommand):
    help = 'Sincroniza lembretes derivados e envia por e-mail os que já venceram.'

    def handle(self, *args, **options):
        now = timezone.now()
        synced = 0
        for user in User.objects.filter(is_active=True):
            synced += sync_reminders(user)

        due = Reminder.objects.filter(
            status=Reminder.Status.PENDING, remind_at__lte=now,
        ).select_related('user')

        sent = 0
        for reminder in due:
            send_mail(
                subject=f'Vitalis · {reminder.title}',
                message=reminder.description or reminder.get_category_display(),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[reminder.user.email],
                fail_silently=False,
            )
            reminder.status = Reminder.Status.SENT
            reminder.sent_at = now
            reminder.save(update_fields=['status', 'sent_at', 'updated_at'])
            sent += 1

        self.stdout.write(self.style.SUCCESS(
            f'{synced} lembretes sincronizados, {sent} enviados.'
        ))
