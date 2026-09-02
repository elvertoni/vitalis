"""
Health domain: doctors, treatments, exams, appointments and medication.

Every model here holds personal health data, so every one of them inherits from
``OwnedModel`` and is reached only through the isolation mixins in ``core.mixins``.
"""

from datetime import date, timedelta

from django.db import models
from django.urls import reverse
from django.utils import timezone

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
        indexes = [
            models.Index(fields=['user', '-requested_date']),
            models.Index(fields=['user', 'scheduled_date']),
        ]

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
# Dias da semana como o Python conta (segunda = 0), para a periodicidade do medicamento.
WEEKDAY_LABELS = {0: 'Seg', 1: 'Ter', 2: 'Qua', 3: 'Qui', 4: 'Sex', 5: 'Sáb', 6: 'Dom'}
WEEKDAY_CHOICES = [
    (0, 'Segunda'), (1, 'Terça'), (2, 'Quarta'), (3, 'Quinta'),
    (4, 'Sexta'), (5, 'Sábado'), (6, 'Domingo'),
]

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
        indexes = [
            models.Index(fields=['user', '-date']),
            models.Index(fields=['user', 'next_return_date']),
        ]

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
    weekdays = models.JSONField(
        'dias da semana',
        default=list,
        blank=True,
        help_text='Em branco, todo dia. Marque os dias para remédio semanal.',
    )
    is_active = models.BooleanField('em uso', default=True)
    cycle_daily_days = models.PositiveSmallIntegerField(
        'dias da fase diária',
        null=True,
        blank=True,
        help_text='Só para esquema em fases. Ex.: 30 dias todo dia e depois dias alternados.',
    )
    cycle_alternates_after = models.BooleanField(
        'alterna dias depois',
        default=False,
        help_text='Terminada a fase diária, passa a tomar em dias alternados.',
    )

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
        """
        Whether a dose is due on ``day``.

        Three things can rule the day out, in order of how coarse they are: the course has
        not started or has ended, the weekly schedule does not include that weekday, or the
        two-phase cycle says today is a skip day. A weekly medicine (``weekdays``) is the
        reason this is not simply a date range: a shot taken every Tuesday must not raise a
        reminder on the other six days.
        """
        if not self.is_active or self.start_date > day:
            return False
        if self.end_date is not None and day > self.end_date:
            return False
        if self.weekdays and day.weekday() not in self.weekdays:
            return False
        return self.takes_on_cycle_day(day)

    def takes_on_cycle_day(self, day):
        """False only on the skip day of a two-phase course; True for everything else."""
        if not self.cycle_daily_days or not self.cycle_alternates_after:
            return True
        elapsed = (day - self.start_date).days
        if elapsed < self.cycle_daily_days:
            return True
        return (elapsed - self.cycle_daily_days) % 2 == 0

    @property
    def weekdays_display(self):
        """``Seg, Qui`` — or empty when the medicine is taken every day."""
        if not self.weekdays:
            return ''
        return ', '.join(WEEKDAY_LABELS[d] for d in sorted(self.weekdays) if d in WEEKDAY_LABELS)

    @property
    def times_display(self):
        return ', '.join(self.schedule_times) if self.schedule_times else ''

    @property
    def cycle_status(self):
        """
        Which phase of a two-phase course the medicine is in today.

        The schedule is described by the row, never by the drug's name in code:
        ``cycle_daily_days`` is how long the every-day phase lasts and
        ``cycle_alternates_after`` says whether every-other-day follows it. A continuous
        medicine returns ``None`` and the screen shows no badge at all.
        """
        if not self.cycle_daily_days:
            return None

        today = timezone.localdate()
        elapsed = (today - self.start_date).days
        if elapsed < 0:
            return {'text': f'Inicia em {self.start_date:%d/%m}', 'active': False, 'phase': 'pending'}
        if elapsed < self.cycle_daily_days:
            return {
                'text': f'Fase diária · dia {elapsed + 1} de {self.cycle_daily_days}',
                'active': True,
                'phase': 'daily',
            }
        if not self.cycle_alternates_after:
            return None
        if (elapsed - self.cycle_daily_days) % 2 == 0:
            return {'text': 'Dias alternados · hoje toma', 'active': True, 'phase': 'alternate_take'}
        return {'text': 'Dias alternados · hoje pula', 'active': False, 'phase': 'alternate_skip'}


class LabPanel(OwnedModel):
    """
    A block of the lab report — the haemogram, the lipid profile — as it is printed.

    A panel exists so the reading of an ``Exam`` can be shown as gauges instead of a wall of
    numbers. It hangs off the exam it came from, which is what carries the PDF and the
    requesting doctor; a panel typed by hand before the report arrives simply has no exam.
    """

    class SampleKind(models.TextChoices):
        EDTA = 'edta', 'Tubo EDTA'
        FLUORIDE = 'fluoreto', 'Fluoreto'
        SERUM = 'soro', 'Soro'
        URINE = 'urina', 'Urina'
        OTHER = 'outro', 'Outro'

    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='lab_panels',
        verbose_name='exame',
    )
    title = models.CharField('título', max_length=140, help_text='Ex.: hemograma completo.')
    sample_kind = models.CharField(
        'material',
        max_length=10,
        choices=SampleKind.choices,
        default=SampleKind.SERUM,
    )
    sample_label = models.CharField(
        'etiqueta do material',
        max_length=40,
        blank=True,
        help_text='O selo que aparece no cartão. Em branco, usa o nome do material.',
    )
    method = models.CharField(
        'material e método',
        max_length=180,
        blank=True,
        help_text='Como está no laudo. Ex.: sangue total com EDTA · citometria de fluxo.',
    )
    order = models.PositiveSmallIntegerField('ordem', default=1)

    class Meta:
        verbose_name = 'painel laboratorial'
        verbose_name_plural = 'painéis laboratoriais'
        ordering = ['order', 'title']
        indexes = [models.Index(fields=['user', 'order'])]

    def __str__(self):
        return self.title

    @property
    def badge(self):
        return self.sample_label or self.get_sample_kind_display()


class LabResult(OwnedModel):
    """
    One measured biomarker, with the scale needed to draw it.

    Four numbers describe the gauge: ``scale_min``/``scale_max`` are the ends of the drawn
    ruler and ``ref_low``/``ref_high`` the normal band inside it. They are stored, not derived,
    because the reference band belongs to the laboratory that issued the report — the same
    analyte reads differently between labs, and a value is only out of range against the
    range printed beside it.

    ``previous_value`` is the reading this one is compared against. Frozen on purpose: it comes
    from a report that will never change, which is the exception the macro rule in ``nutricao``
    describes — freeze what an outside source issued, compute what the person still edits.
    """

    class Status(models.TextChoices):
        OK = 'ok', 'Na meta'
        WATCH = 'watch', 'Atenção'
        OUT = 'out', 'Fora da meta'

    panel = models.ForeignKey(
        LabPanel,
        on_delete=models.CASCADE,
        related_name='results',
        verbose_name='painel',
    )
    name = models.CharField('exame', max_length=140)
    unit = models.CharField('unidade', max_length=20, blank=True)
    value = models.DecimalField('resultado', max_digits=12, decimal_places=3)
    previous_value = models.DecimalField(
        'resultado anterior',
        max_digits=12,
        decimal_places=3,
        null=True,
        blank=True,
    )
    previous_label = models.CharField(
        'quando foi o anterior',
        max_length=40,
        blank=True,
        help_text='Ex.: dez/25.',
    )
    scale_min = models.DecimalField('início da régua', max_digits=12, decimal_places=3)
    scale_max = models.DecimalField('fim da régua', max_digits=12, decimal_places=3)
    ref_low = models.DecimalField('referência mínima', max_digits=12, decimal_places=3)
    ref_high = models.DecimalField('referência máxima', max_digits=12, decimal_places=3)
    status = models.CharField('situação', max_length=6, choices=Status.choices, default=Status.OK)
    note = models.CharField('observação', max_length=200, blank=True)
    decimals = models.PositiveSmallIntegerField('casas decimais', default=1)
    order = models.PositiveSmallIntegerField('ordem', default=1)

    class Meta:
        verbose_name = 'resultado laboratorial'
        verbose_name_plural = 'resultados laboratoriais'
        ordering = ['panel', 'order', 'id']

    def __str__(self):
        return f'{self.name}: {self.display_value} {self.unit}'.strip()

    # ── Régua ────────────────────────────────────────────────────────────────
    # Posições em porcentagem da largura da régua, prontas para o ``style`` do template.
    # Ficam aqui, e não na view, porque dependem só da linha: qualquer tela que mostrar o
    # resultado desenha a mesma régua sem repetir a conta.

    def _position(self, value):
        """Where ``value`` sits on the drawn ruler, clamped so the dot never leaves the track."""
        if value is None:
            return None
        span = float(self.scale_max) - float(self.scale_min)
        if span == 0:
            return 50.0
        percent = ((float(value) - float(self.scale_min)) / span) * 100.0
        return max(2.0, min(98.0, percent))

    @property
    def position(self):
        return self._position(self.value)

    @property
    def ref_low_position(self):
        return self._position(self.ref_low)

    @property
    def ref_high_position(self):
        return self._position(self.ref_high)

    @property
    def ref_width(self):
        return max(2.0, self.ref_high_position - self.ref_low_position)

    @property
    def previous_position(self):
        return self._position(self.previous_value)

    @property
    def trail_left(self):
        """Left edge of the dashed trail joining the previous reading to this one."""
        if self.previous_value is None:
            return None
        return min(self.previous_position, self.position)

    @property
    def trail_width(self):
        if self.previous_value is None:
            return None
        return max(1.0, abs(self.position - self.previous_position))

    @property
    def variation(self):
        """Signed percentage against the previous reading, already formatted."""
        if not self.previous_value:
            return None
        delta = ((float(self.value) - float(self.previous_value)) / float(self.previous_value)) * 100.0
        return f'{delta:+.1f}%'

    def _format(self, value):
        if value is None:
            return ''
        return f'{float(value):.{self.decimals}f}'.replace('.', ',')

    @property
    def display_value(self):
        return self._format(self.value)

    @property
    def display_previous(self):
        return self._format(self.previous_value)

    @property
    def display_ref_low(self):
        return self._format(self.ref_low)

    @property
    def display_ref_high(self):
        return self._format(self.ref_high)


class ClinicalNote(OwnedModel):
    """
    A written observation that belongs to the person, not to a single row of the report.

    Two kinds share the model because they differ only in where they are shown: ``ALERT`` is
    what to watch now, ``ALIGNMENT`` is what to raise at the next appointment. Both are text
    someone wrote after reading the results, so neither can be derived from ``LabResult`` —
    a value inside the reference band can still deserve a conversation.
    """

    class Kind(models.TextChoices):
        ALERT = 'alert', 'Ponto de atenção'
        ALIGNMENT = 'alignment', 'Alinhar com o médico'

    class Severity(models.TextChoices):
        CRITICAL = 'critical', 'Crítico'
        WARNING = 'warning', 'Atenção'
        POSITIVE = 'positive', 'Evolução boa'
        INFO = 'info', 'Informativo'

    kind = models.CharField('tipo', max_length=10, choices=Kind.choices, default=Kind.ALERT)
    severity = models.CharField('gravidade', max_length=10, choices=Severity.choices, default=Severity.INFO)
    title = models.CharField('título', max_length=140)
    body = models.TextField('texto')
    icon = models.CharField(
        'ícone',
        max_length=40,
        blank=True,
        help_text='Nome do ícone Lucide. Ex.: shield-alert.',
    )
    order = models.PositiveSmallIntegerField('ordem', default=1)

    class Meta:
        verbose_name = 'nota clínica'
        verbose_name_plural = 'notas clínicas'
        ordering = ['kind', 'order', 'id']
        indexes = [models.Index(fields=['user', 'kind', 'order'])]

    def __str__(self):
        return self.title
