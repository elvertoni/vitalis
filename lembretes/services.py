"""
Regenerates derived reminders from the domain data that actually defines them.

Four of the five categories in the PRD have a real schedule to read from: medication times,
a scheduled exam, an appointment's return date, a planned meal's time. Training has none —
see ``DECISIONS.md`` D-027 for why no ``Reminder`` is auto-generated for it.

``sync_reminders`` is deliberately a wipe-and-recreate for the derived slice of a user's
pending reminders inside the lookahead window, not an incremental upsert: it is simpler,
never drifts when a source record changes (an appointment's return date gets pushed a week,
the old reminder just isn't recreated), and is safe to call as often as needed — from the
central's own page view, and from the ``send_due_reminders`` command right before it sends.
Manual reminders (``content_type`` is null) and reminders already sent/done/cancelled are
never touched.
"""

from datetime import datetime, time, timedelta

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from nutricao.models import Diet, Meal
from saude.models import Appointment, Exam, Medication

from .models import Reminder

DEFAULT_TIME = time(8, 0)  # exame e retorno não têm horário próprio; lembra de manhã.
LOOKAHEAD_DAYS = 7


def _aware(day, at_time):
    return timezone.make_aware(datetime.combine(day, at_time))


def sync_reminders(user, horizon_days=LOOKAHEAD_DAYS):
    """Rebuilds every derived, still-pending reminder for ``user`` within the next days."""
    today = timezone.localdate()
    horizon = today + timedelta(days=horizon_days)
    window_start = timezone.make_aware(datetime.combine(today, time.min))
    window_end = timezone.make_aware(datetime.combine(horizon, time.max))

    Reminder.objects.filter(
        user=user, status=Reminder.Status.PENDING, content_type__isnull=False,
        remind_at__gte=window_start, remind_at__lte=window_end,
    ).delete()

    batch = []
    batch += _medication_reminders(user, today, horizon)
    batch += _exam_reminders(user, today, horizon)
    batch += _appointment_reminders(user, today, horizon)
    batch += _meal_reminders(user, today, horizon)
    Reminder.objects.bulk_create(batch)
    return len(batch)


def _medication_reminders(user, today, horizon):
    content_type = ContentType.objects.get_for_model(Medication)
    reminders = []
    for medication in Medication.objects.filter(user=user, is_active=True):
        day = today
        while day <= horizon:
            if medication.is_current_on(day):
                for time_str in medication.schedule_times:
                    hh, mm = (int(part) for part in time_str.split(':'))
                    reminders.append(Reminder(
                        user=user, category=Reminder.Category.MEDICATION,
                        title=medication.name,
                        description=f'{medication.dosage} · {medication.frequency}'.strip(' ·'),
                        remind_at=_aware(day, time(hh, mm)),
                        is_recurring=True, recurrence_rule=medication.frequency or 'diário',
                        content_type=content_type, object_id=medication.pk,
                    ))
            day += timedelta(days=1)
    return reminders


def _exam_reminders(user, today, horizon):
    content_type = ContentType.objects.get_for_model(Exam)
    reminders = []
    for exam in Exam.objects.filter(
        user=user, scheduled_date__gte=today, scheduled_date__lte=horizon, done_date__isnull=True,
    ).select_related('doctor'):
        reminders.append(Reminder(
            user=user, category=Reminder.Category.EXAM, title=exam.name,
            description=f'Agendado com {exam.doctor}' if exam.doctor else 'Exame agendado',
            remind_at=_aware(exam.scheduled_date, DEFAULT_TIME),
            content_type=content_type, object_id=exam.pk,
        ))
    return reminders


def _appointment_reminders(user, today, horizon):
    content_type = ContentType.objects.get_for_model(Appointment)
    reminders = []
    for appointment in Appointment.objects.filter(
        user=user, next_return_date__gte=today, next_return_date__lte=horizon,
    ).select_related('doctor'):
        reminders.append(Reminder(
            user=user, category=Reminder.Category.RETURN,
            title=f'Retorno · {appointment.doctor}',
            description=appointment.reason,
            remind_at=_aware(appointment.next_return_date, DEFAULT_TIME),
            content_type=content_type, object_id=appointment.pk,
        ))
    return reminders


def _meal_reminders(user, today, horizon):
    """One occurrence per day, per meal with a time set, only for the active diet."""
    active_diet = Diet.objects.filter(user=user, is_active=True).prefetch_related('meals').first()
    if active_diet is None:
        return []
    content_type = ContentType.objects.get_for_model(Meal)
    meals = [meal for meal in active_diet.meals.all() if meal.time]
    reminders = []
    day = today
    while day <= horizon:
        for meal in meals:
            reminders.append(Reminder(
                user=user, category=Reminder.Category.NUTRITION, title=meal.name,
                description=f'Refeição do plano {active_diet.name}',
                remind_at=_aware(day, meal.time),
                is_recurring=True, recurrence_rule='diário, conforme a dieta ativa',
                content_type=content_type, object_id=meal.pk,
            ))
        day += timedelta(days=1)
    return reminders
