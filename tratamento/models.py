"""
Injectable treatment domain: each shot actually given and the side effects that follow.

``saude.Medication`` already says *when* a dose is due (``weekdays`` + ``is_current_on``).
This app records what *happened*: the shot, at which dose and where, and how the person
felt afterwards. The dose lives on each ``Injection`` and not only on the medication
because injectable courses step the dose up over time (titration); a single text field
on ``Medication`` would erase that history.

Body composition (fat, lean mass, water, waist) is not here: it rides on
``nutricao.WeightLog`` as optional columns, so the weekly check-in is one row.
"""

from datetime import timedelta
from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

from core.models import OwnedModel
from saude.models import Medication


class Injection(OwnedModel):
    """One shot given. The row the schedule, the site rotation and the dose history read."""

    class Site(models.TextChoices):
        ABDOMEN_LEFT = 'abdomen_left', 'Abdômen esquerdo'
        ABDOMEN_RIGHT = 'abdomen_right', 'Abdômen direito'
        THIGH_LEFT = 'thigh_left', 'Coxa esquerda'
        THIGH_RIGHT = 'thigh_right', 'Coxa direita'
        ARM_LEFT = 'arm_left', 'Braço esquerdo'
        ARM_RIGHT = 'arm_right', 'Braço direito'

    medication = models.ForeignKey(
        Medication,
        on_delete=models.CASCADE,
        related_name='injections',
        verbose_name='medicamento',
    )
    applied_at = models.DateTimeField('aplicada em', default=timezone.now)
    dose_mg = models.DecimalField(
        'dose (mg)',
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text='Como está na caneta. Ex.: 2,5 ou 0,25.',
    )
    site = models.CharField('local', max_length=16, choices=Site.choices)
    notes = models.CharField('observação', max_length=200, blank=True)

    class Meta:
        verbose_name = 'aplicação'
        verbose_name_plural = 'aplicações'
        ordering = ['-applied_at']
        indexes = [models.Index(fields=['user', '-applied_at'])]

    def __str__(self):
        return f'{self.medication.name} · {self.dose_mg} mg · {timezone.localtime(self.applied_at):%d/%m/%Y}'

    def get_absolute_url(self):
        return reverse('tratamento:injection_update', args=[self.pk])

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Registrar uma aplicação é a prova de que o medicamento é injetável: marca a flag
        # que decide o cartão do painel e a categoria do lembrete (D-071).
        if not self.medication.is_injectable:
            Medication.objects.filter(pk=self.medication_id).update(is_injectable=True)
            self.medication.is_injectable = True


class SideEffect(OwnedModel):
    """
    How the person felt on a given day. ``injection`` is optional on purpose: nausea on
    day three belongs to the week's shot, but a headache may be unrelated, and forcing
    the link would make the cross-reference lie.
    """

    class Kind(models.TextChoices):
        NAUSEA = 'nausea', 'Náusea'
        VOMITING = 'vomiting', 'Vômito'
        DIARRHEA = 'diarrhea', 'Diarreia'
        CONSTIPATION = 'constipation', 'Prisão de ventre'
        REFLUX = 'reflux', 'Refluxo ou azia'
        ABDOMINAL_PAIN = 'abdominal_pain', 'Dor abdominal'
        FATIGUE = 'fatigue', 'Cansaço'
        HEADACHE = 'headache', 'Dor de cabeça'
        DIZZINESS = 'dizziness', 'Tontura'
        SITE_REACTION = 'site_reaction', 'Reação no local'
        OTHER = 'other', 'Outro'

    class Intensity(models.IntegerChoices):
        MILD = 1, 'Leve'
        MODERATE = 2, 'Moderada'
        STRONG = 3, 'Forte'

    date = models.DateField('data', default=timezone.localdate)
    kind = models.CharField('sintoma', max_length=16, choices=Kind.choices)
    intensity = models.PositiveSmallIntegerField('intensidade', choices=Intensity.choices)
    injection = models.ForeignKey(
        Injection,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='side_effects',
        verbose_name='aplicação relacionada',
    )
    notes = models.CharField('observação', max_length=200, blank=True)

    class Meta:
        verbose_name = 'efeito colateral'
        verbose_name_plural = 'efeitos colaterais'
        ordering = ['-date', '-id']
        indexes = [models.Index(fields=['user', '-date'])]

    def __str__(self):
        return f'{self.get_kind_display()} · {self.get_intensity_display()} · {self.date:%d/%m/%Y}'

    def get_absolute_url(self):
        return reverse('tratamento:sideeffect_update', args=[self.pk])


def next_due_date(medication, today=None, horizon_days=14):
    """
    The next day ``medication`` has a dose, from ``today`` on, or ``None`` inside the horizon.

    Reuses ``Medication.is_current_on`` so the Home card and the reminder generator can
    never disagree about which day the shot is.
    """
    today = today or timezone.localdate()
    for offset in range(horizon_days + 1):
        day = today + timedelta(days=offset)
        if medication.is_current_on(day):
            return day
    return None


def missed_due_date(medication, today=None, lookback_days=14):
    """
    The most recent past dose day with no shot recorded on or after it, or ``None``.

    "On or after" because a shot given a day late still covers that week: Tuesday's dose
    applied on Wednesday must not leave Tuesday flagged as missed. Only days after the
    medication's start count, so a course begun yesterday never starts out late.
    """
    today = today or timezone.localdate()
    for offset in range(1, lookback_days + 1):
        day = today - timedelta(days=offset)
        if medication.is_current_on(day):
            covered = Injection.objects.filter(
                user=medication.user, medication=medication, applied_at__date__gte=day
            ).exists()
            return None if covered else day
    return None


def suggested_site(user, medication):
    """
    The site used longest ago (or never) for this medication: rotating avoids lumps under
    the skin. A suggestion shown in the form, never written on its own.
    """
    last_used = {}
    for site, applied_at in (
        Injection.objects.filter(user=user, medication=medication)
        .values_list('site', 'applied_at')
    ):
        if site not in last_used or applied_at > last_used[site]:
            last_used[site] = applied_at
    unused = [site for site in Injection.Site.values if site not in last_used]
    if unused:
        return unused[0]
    return min(last_used, key=last_used.get)
