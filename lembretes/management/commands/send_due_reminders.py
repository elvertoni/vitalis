"""
The dispatcher: run this from the scheduler every few minutes.

Two steps, per active user: resync their derived reminders (so a medication added five
minutes ago is already covered), then send whatever is pending, due **and worth an
interruption**. That last filter is ``lembretes.notifications.NOTIFY_CATEGORIES``: only
things with no date booked yet go out, the rest stays on screen (D-044). The wording and the
channel belong to that module too — this command decides *when*, not *what* or *how*.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from lembretes.models import Reminder
from lembretes.notifications import NOTIFY_CATEGORIES, send_reminder
from lembretes.services import sync_reminders

User = get_user_model()


class Command(BaseCommand):
    help = 'Sincroniza lembretes derivados e envia por e-mail os que já venceram.'

    def handle(self, *args, **options):
        now = timezone.now()
        synced = 0
        for user in User.objects.filter(is_active=True):
            synced += sync_reminders(user)

        pending_due = Reminder.objects.filter(
            status=Reminder.Status.PENDING, remind_at__lte=now,
        ).select_related('user')
        due = pending_due.filter(category__in=NOTIFY_CATEGORIES)
        on_screen_only = pending_due.exclude(category__in=NOTIFY_CATEGORIES).count()

        sent = 0
        for reminder in due:
            send_reminder(reminder)
            reminder.status = Reminder.Status.SENT
            reminder.sent_at = now
            reminder.save(update_fields=['status', 'sent_at', 'updated_at'])
            sent += 1

        self.stdout.write(self.style.SUCCESS(
            f'{synced} lembretes sincronizados, {sent} enviados, '
            f'{on_screen_only} vencidos que ficam só na tela.'
        ))
