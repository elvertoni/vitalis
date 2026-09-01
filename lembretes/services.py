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
never touched — and, just as importantly, never recreated either: see
``_drop_already_handled``, without which every run would remail the day's past reminders.
"""

from datetime import datetime, time, timedelta

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from nutricao.models import Diet, Meal
from saude.models import (
    EXAM_SCHEDULING_LEAD_DAYS,
    EXAM_SCHEDULING_MAX_NOTICES,
    EXAM_SCHEDULING_REPEAT_DAYS,
    RETURN_SCHEDULING_LEAD_DAYS,
    TREATMENT_CHECKUP_INTERVAL_DAYS,
    Appointment,
    Exam,
    Medication,
    Treatment,
)

from .models import Reminder

DEFAULT_TIME = time(8, 0)  # exame e retorno não têm horário próprio; lembra de manhã.
LOOKAHEAD_DAYS = 7


def _aware(day, at_time):
    return timezone.make_aware(datetime.combine(day, at_time))


def sync_reminders(user, horizon_days=LOOKAHEAD_DAYS):
    """
    Rebuilds every derived, still-pending reminder for ``user`` within the next days.

    Free plan (PRD 10.2, "sem lembretes automáticos"): this clears any derived reminder
    instead of generating new ones. Manual reminders are untouched either way — the limit
    is specifically on the *automatic* kind.
    """
    from billing.gating import auto_reminders_enabled

    if not auto_reminders_enabled(user):
        return clear_derived_reminders(user)

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
    batch += _return_scheduling_reminders(user, today, horizon)
    batch += _exam_scheduling_reminders(user, today, horizon)
    batch += _treatment_checkup_reminders(user, today, horizon)
    batch += _meal_reminders(user, today, horizon)
    batch = _drop_already_handled(user, batch, window_start, window_end)
    Reminder.objects.bulk_create(batch)
    return len(batch)


def _drop_already_handled(user, batch, window_start, window_end):
    """
    Keeps the wipe-and-recreate from resurrecting reminders that are already done with.

    The wipe above only deletes *pending* rows, which is what makes the rebuild safe. But a
    row that left that state stays in the table, and regenerating it would create a second,
    pending copy of something already handled: this morning's 07:00 dose, sent an hour ago,
    would be recreated overdue and mailed again on the next run — every run, all day. The
    same applies to a reminder the person ticked off or cancelled by hand.

    Identity is the source record plus the exact instant, which is what the generators
    derive deterministically from the domain data (see DECISIONS.md D-043).
    """
    handled = set(
        Reminder.objects.filter(
            user=user, content_type__isnull=False,
            remind_at__gte=window_start, remind_at__lte=window_end,
        )
        .exclude(status=Reminder.Status.PENDING)
        .values_list('content_type_id', 'object_id', 'remind_at')
    )
    if not handled:
        return batch
    return [
        reminder for reminder in batch
        if (reminder.content_type_id, reminder.object_id, reminder.remind_at) not in handled
    ]


def clear_derived_reminders(user):
    """Removes every pending derived reminder — used when the plan doesn't allow them."""
    deleted, _ = Reminder.objects.filter(user=user, status=Reminder.Status.PENDING, content_type__isnull=False).delete()
    return deleted


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


def _return_scheduling_reminders(user, today, horizon):
    """
    "Call and book the return", ``RETURN_SCHEDULING_LEAD_DAYS`` days before the asked date.

    The reminder for the return itself lands on the day, too late to still find a slot in a
    specialist's diary. This one lands early, and goes away on its own once a later visit to
    the same doctor exists: the return was booked (or already happened) and asking again
    would be noise. Hence only the most recent visit per doctor is considered.

    Like every derived reminder, the notice day has to fall inside the sync window. With
    ``send_due_reminders`` running daily (D-030) it always does; with no sync at all for
    several days in a row a notice can be missed — deliberately, since recreating overdue
    notices on every visit would pile up duplicates (see DECISIONS.md D-042).
    """
    content_type = ContentType.objects.get_for_model(Appointment)
    latest_by_doctor = {}
    for visit in Appointment.objects.filter(user=user).select_related('doctor'):
        current = latest_by_doctor.get(visit.doctor_id)
        if current is None or (visit.date, visit.pk) > (current.date, current.pk):
            latest_by_doctor[visit.doctor_id] = visit

    reminders = []
    for visit in latest_by_doctor.values():
        if not visit.next_return_date:
            continue
        remind_day = visit.next_return_date - timedelta(days=RETURN_SCHEDULING_LEAD_DAYS)
        if not today <= remind_day <= horizon:
            continue
        reminders.append(Reminder(
            user=user, category=Reminder.Category.SCHEDULING,
            title=f'Não se esqueça de agendar seu retorno com {visit.doctor}',
            description=(
                f'O médico pediu o retorno para {visit.next_return_date:%d/%m/%Y}. '
                'Ligue para marcar enquanto há vaga.'
            ),
            remind_at=_aware(remind_day, DEFAULT_TIME),
            content_type=content_type, object_id=visit.pk,
        ))
    return reminders


def _exam_scheduling_reminders(user, today, horizon):
    """
    "Book the exam the doctor ordered", for every request still without a date.

    ``_exam_reminders`` only covers an exam that already has a day marked — the request that
    nobody ever booked was invisible, which is exactly the one worth chasing. Starts
    ``EXAM_SCHEDULING_LEAD_DAYS`` after the request (people do book it themselves in the
    first days) and repeats weekly while the exam has no date, up to
    ``EXAM_SCHEDULING_MAX_NOTICES`` times: a request nobody acted on for two months is stale,
    not urgent, and nagging forever trains the person to ignore the whole channel.
    """
    content_type = ContentType.objects.get_for_model(Exam)
    reminders = []
    for exam in Exam.objects.filter(
        user=user, scheduled_date__isnull=True, done_date__isnull=True,
    ).select_related('doctor'):
        day = exam.requested_date + timedelta(days=EXAM_SCHEDULING_LEAD_DAYS)
        for _ in range(EXAM_SCHEDULING_MAX_NOTICES):
            if day > horizon:
                break
            if day >= today:
                asked_by = f'Solicitado por {exam.doctor}' if exam.doctor else 'Solicitado'
                reminders.append(Reminder(
                    user=user, category=Reminder.Category.SCHEDULING,
                    title=f'Não se esqueça de agendar seu exame: {exam.name}',
                    description=f'{asked_by} em {exam.requested_date:%d/%m/%Y}, e ainda sem data marcada.',
                    remind_at=_aware(day, DEFAULT_TIME),
                    content_type=content_type, object_id=exam.pk,
                ))
            day += timedelta(days=EXAM_SCHEDULING_REPEAT_DAYS)
    return reminders


def _treatment_checkup_reminders(user, today, horizon):
    """
    "Book your next appointment", for a treatment that is running with nothing scheduled.

    Only fires when the treatment is open, has no upcoming visit and no pending return date —
    those two already have their own notice, and a third one saying the same thing is noise.
    Anchored on the last visit of that treatment (or its start date) and repeated every
    ``TREATMENT_CHECKUP_INTERVAL_DAYS``, so the cadence is predictable instead of drifting
    with whenever the sync happened to run.
    """
    content_type = ContentType.objects.get_for_model(Treatment)
    reminders = []
    for treatment in Treatment.objects.filter(
        user=user, status=Treatment.Status.ONGOING,
    ).select_related('doctor'):
        visits = list(treatment.appointments.all())
        if any(visit.date >= today for visit in visits):
            continue  # já tem consulta marcada
        if any(visit.next_return_date and visit.next_return_date >= today for visit in visits):
            continue  # o retorno já foi pedido: quem cobra é _return_scheduling_reminders
        last_visit = max((visit.date for visit in visits), default=None)
        anchor = last_visit or treatment.start_date
        elapsed = (today - anchor).days
        periods = max(1, -(-elapsed // TREATMENT_CHECKUP_INTERVAL_DAYS))  # teto da divisão
        day = anchor + timedelta(days=TREATMENT_CHECKUP_INTERVAL_DAYS * periods)
        if not today <= day <= horizon:
            continue
        since = (
            f'A última consulta foi em {last_visit:%d/%m/%Y}.' if last_visit
            else f'Nenhuma consulta registrada desde o início, em {treatment.start_date:%d/%m/%Y}.'
        )
        reminders.append(Reminder(
            user=user, category=Reminder.Category.SCHEDULING,
            title=f'Não se esqueça de agendar sua próxima consulta · {treatment.name}',
            description=since,
            remind_at=_aware(day, DEFAULT_TIME),
            content_type=content_type, object_id=treatment.pk,
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
