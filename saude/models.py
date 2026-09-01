"""
Health domain: doctors, treatments, exams, appointments and medication.

Every model here holds personal health data, so every one of them inherits from
``OwnedModel`` and is reached only through the isolation mixins in ``core.mixins``.
"""

from datetime import date, timedelta

from django.db import models
from django.urls import reverse

from core.models import OwnedModel
from core.validators import attachment_upload_path, validate_attachment


class Doctor(OwnedModel):
    """A professional the person sees. Referenced by treatments, exams and appointments."""

    name = models.CharField('nome', max_length=180)
    specialty = models.CharField('especialidade', max_length=120, blank=True)
    phone = models.CharField('telefone', max_length=20, blank=True)
    email = models.EmailField('e-mail', blank=True)
    clinic_name = models.CharField('clínica', max_length=180, blank=True)
    clinic_address = models.CharField('endereço da clínica', max_length=255, blank=True)
    notes = models.TextField('observações', blank=True)

    class Meta:
        verbose_name = 'médico'
        verbose_name_plural = 'médicos'
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('saude:doctor_detail', args=[self.pk])


class Treatment(OwnedModel):
    """An ongoing course of care that ties exams, appointments and medication together."""

    class Status(models.TextChoices):
        ONGOING = 'ongoing', 'Em andamento'
        FINISHED = 'finished', 'Concluído'
        PAUSED = 'paused', 'Pausado'
        CANCELLED = 'cancelled', 'Cancelado'

    doctor = models.ForeignKey(
        Doctor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='treatments',
        verbose_name='médico responsável',
    )
    name = models.CharField('nome', max_length=180)
    description = models.TextField('descrição', blank=True)
    start_date = models.DateField('início')
    end_date = models.DateField('término', null=True, blank=True, help_text='Em branco enquanto continuar.')
    status = models.CharField('situação', max_length=10, choices=Status.choices, default=Status.ONGOING)
    notes = models.TextField('observações', blank=True)

    class Meta:
        verbose_name = 'tratamento'
        verbose_name_plural = 'tratamentos'
        ordering = ['-start_date']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('saude:treatment_detail', args=[self.pk])

    @property
    def is_open(self):
        return self.status in {self.Status.ONGOING, self.Status.PAUSED}


class Exam(OwnedModel):
    """
    A lab or imaging exam, from the request to the report.

    The attachment is the report itself. It never gets a public URL: the file name is
    random and the download goes through a view that checks ownership first.
    """

    class Status(models.TextChoices):
        REQUESTED = 'requested', 'Solicitado'
        SCHEDULED = 'scheduled', 'Agendado'
        DONE = 'done', 'Realizado'

    doctor = models.ForeignKey(
        Doctor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='exams',
        verbose_name='solicitante',
    )
    treatment = models.ForeignKey(
        Treatment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='exams',
        verbose_name='tratamento',
    )
    name = models.CharField('nome do exame', max_length=180)
    requested_date = models.DateField('solicitado em')
    scheduled_date = models.DateField(
        'agendado para',
        null=True,
        blank=True,
        help_text='Data marcada para a coleta ou o procedimento.',
    )
    done_date = models.DateField('realizado em', null=True, blank=True)
    result_summary = models.TextField(
        'resumo do resultado',
        blank=True,
        help_text='O que está escrito no laudo. Transcrição, não interpretação.',
    )
    attachment = models.FileField(
        'laudo',
        upload_to=attachment_upload_path,
        validators=[validate_attachment],
        null=True,
        blank=True,
        help_text='PDF, JPG ou PNG, até 10 MB.',
    )
    status = models.CharField('situação', max_length=10, choices=Status.choices, default=Status.REQUESTED)

    class Meta:
        verbose_name = 'exame'
        verbose_name_plural = 'exames'
        ordering = ['-requested_date']
        indexes = [models.Index(fields=['user', '-requested_date'])]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('saude:exam_detail', args=[self.pk])

    @property
    def needs_scheduling(self):
        """Requested by a doctor, never booked and never done — nobody marked a date yet."""
        return self.scheduled_date is None and self.done_date is None

    @property
    def relevant_date(self):
        """The date that matters for sorting a timeline: done, else scheduled, else requested."""
        return self.done_date or self.scheduled_date or self.requested_date

    @property
    def is_upcoming(self):
        return bool(self.scheduled_date and not self.done_date and self.scheduled_date >= date.today())


# Ritmo das cobranças de agendamento. Vivem aqui, e não em ``lembretes``, porque as telas de
# saúde precisam das constantes e ``saude`` não pode importar ``lembretes`` (a dependência
# corre no sentido contrário). Ver DECISIONS.md D-042 e D-044.
RETURN_SCHEDULING_LEAD_DAYS = 15      # retorno pedido pelo médico: avisa 15 dias antes
EXAM_SCHEDULING_LEAD_DAYS = 3         # exame solicitado: espera 3 dias antes de cobrar
EXAM_SCHEDULING_REPEAT_DAYS = 7       # e repete semanalmente enquanto não tiver data
EXAM_SCHEDULING_MAX_NOTICES = 8       # por 8 semanas; depois disso a solicitação envelheceu
TREATMENT_CHECKUP_INTERVAL_DAYS = 30  # tratamento em andamento sem nada marcado: mensal


class Appointment(OwnedModel):
    """
    A visit. ``next_return_date`` is what feeds the two return reminders.

    The date the doctor asked the person to come back generates two different nudges:
    one to *book* the slot, ``RETURN_SCHEDULING_LEAD_DAYS`` days ahead, and one for the
    return itself, on the day. Both live in ``lembretes.services``.
    """

    doctor = models.ForeignKey(
        Doctor,
        on_delete=models.CASCADE,
        related_name='appointments',
        verbose_name='médico',
    )
    treatment = models.ForeignKey(
        Treatment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='appointments',
        verbose_name='tratamento',
    )
    date = models.DateField('data')
    reason = models.CharField('motivo', max_length=200, blank=True)
    notes = models.TextField('anotações da consulta', blank=True)
    next_return_date = models.DateField(
        'retorno em',
        null=True,
        blank=True,
        help_text=(
            'Quando o médico pediu para voltar. Vira dois lembretes: um 15 dias antes, '
            'para você marcar a consulta, e outro no dia.'
        ),
    )

    class Meta:
        verbose_name = 'consulta'
        verbose_name_plural = 'consultas'
        ordering = ['-date']
        indexes = [models.Index(fields=['user', '-date'])]

    def __str__(self):
        return f'{self.doctor} · {self.date:%d/%m/%Y}'

    def get_absolute_url(self):
        return reverse('saude:appointment_detail', args=[self.pk])

    @property
    def return_is_pending(self):
        return bool(self.next_return_date and self.next_return_date >= date.today())

    @property
    def return_scheduling_date(self):
        """The day the "book your return" reminder fires. ``None`` without a return date."""
        if not self.next_return_date:
            return None
        return self.next_return_date - timedelta(days=RETURN_SCHEDULING_LEAD_DAYS)

    @property
    def return_is_booked(self):
        """
        Whether a later visit to the same doctor already exists.

        If it does, the return was booked (or already happened) and nagging the person to
        book it again would be noise — only the most recent visit per doctor is nagged.
        """
        return (
            Appointment.objects.filter(user_id=self.user_id, doctor_id=self.doctor_id, date__gt=self.date)
            .exclude(pk=self.pk)
            .exists()
        )


class Medication(OwnedModel):
    """
    A medicine in use, with the times of day it should be taken.

    ``schedule_times`` holds a list of ``HH:MM`` strings. It is a list and not a single
    field because the same medicine often has more than one dose a day, and each one
    becomes its own reminder.
    """

    treatment = models.ForeignKey(
        Treatment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='medications',
        verbose_name='tratamento',
    )
    name = models.CharField('nome', max_length=180)
    dosage = models.CharField('dose', max_length=80, blank=True, help_text='Ex.: 1 comprimido, 50 mg.')
    frequency = models.CharField(
        'frequência',
        max_length=80,
        blank=True,
        help_text='Como está na receita. Ex.: 8/8h, 1x ao dia.',
    )
    start_date = models.DateField('início')
    end_date = models.DateField('término', null=True, blank=True, help_text='Em branco para uso contínuo.')
    schedule_times = models.JSONField(
        'horários',
        default=list,
        blank=True,
        help_text='Horários do dia, separados por vírgula. Ex.: 08:00, 20:00.',
    )
    is_active = models.BooleanField('em uso', default=True)

    class Meta:
        verbose_name = 'medicamento'
        verbose_name_plural = 'medicamentos'
        ordering = ['-is_active', 'name']
        indexes = [models.Index(fields=['user', 'is_active'])]

    def __str__(self):
        return f'{self.name} {self.dosage}'.strip()

    def get_absolute_url(self):
        return reverse('saude:medication_detail', args=[self.pk])

    def is_current_on(self, day):
        """Whether the medicine is in use on a given day."""
        if not self.is_active or self.start_date > day:
            return False
        return self.end_date is None or day <= self.end_date

    @property
    def times_display(self):
        return ', '.join(self.schedule_times) if self.schedule_times else ''
