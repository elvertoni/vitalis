"""
The dispatcher: run this from the scheduler every few minutes.

Two steps, per active user: resync their derived reminders (so a medication added five
minutes ago is already covered), then send whatever is pending, due **and worth an
interruption**. That last filter is ``lembretes.notifications.should_notify``, which asks the
person's own per-category channel preference (D-054): what has no channel open stays on
screen and is never marked as sent. The wording and the channel belong to that module too —
this command decides *when*, not *what* or *how*.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from lembretes.models import Reminder
from lembretes.notifications import send_reminder, should_notify
from lembretes.services import sync_reminders

User = get_user_model()


class Command(BaseCommand):
    help = 'Sincroniza lembretes derivados e envia os que já venceram, pelo canal escolhido.'

    def handle(self, *args, **options):
        now = timezone.now()
        synced = 0
        for user in User.objects.filter(is_active=True):
            synced += sync_reminders(user)

        pending_due = Reminder.objects.filter(
            status=Reminder.Status.PENDING, remind_at__lte=now,
        ).select_related('user', 'user__profile')

        sent = 0
        on_screen_only = 0
        failed = 0
        for reminder in pending_due:
            # A preferência é por pessoa, então o filtro não cabe no queryset: é uma consulta
            # por dono e categoria, resolvida em ``should_notify``.
            if not should_notify(reminder):
                on_screen_only += 1
                continue

            channel = send_reminder(reminder)
            if channel is None:
                # Nada saiu — gateway fora do ar sem e-mail autorizado, por exemplo. Deixa
                # pendente para a próxima rodada em vez de marcar como enviado e perder.
                failed += 1
                continue

            reminder.status = Reminder.Status.SENT
            reminder.sent_at = now
            reminder.save(update_fields=['status', 'sent_at', 'updated_at'])
            sent += 1

        resumo = (
            f'{synced} lembretes sincronizados, {sent} enviados, '
            f'{on_screen_only} vencidos que ficam só na tela.'
        )
        if failed:
            resumo += f' {failed} não saíram e seguem pendentes.'
            self.stdout.write(self.style.WARNING(resumo))
        else:
            self.stdout.write(self.style.SUCCESS(resumo))
