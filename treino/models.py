"""
Training domain: muscle groups, exercises, routines and the sessions actually performed.

Every model here is personal, so every one of them inherits from ``OwnedModel`` — including
the ones nested under a routine or a session (``RoutineDay``, ``RoutineExerciseTarget``,
``SessionEntry``, ``SetLog``). The owner column is denormalized on purpose: it lets
``OwnerFormMixin`` narrow every relational field's queryset without walking a join, the same
pattern ``_legado_vida`` used for ``Resultado.paciente``.
"""

from datetime import timedelta

from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

from core.models import OwnedModel


class MuscleGroup(OwnedModel):
    """Peito, costas, perna... A pessoa começa com uma lista própria, sem catálogo global."""

    name = models.CharField('nome', max_length=80)

    class Meta:
        verbose_name = 'grupo muscular'
        verbose_name_plural = 'grupos musculares'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['user', 'name'], name='grupo_unico_por_usuario'),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('treino:muscle_group_detail', args=[self.pk])


class Exercise(OwnedModel):
    """A movement the person does, tied to the muscle group it trains."""

    class Type(models.TextChoices):
        STRENGTH = 'strength', 'Força'
        CARDIO = 'cardio', 'Cardio'
        MOBILITY = 'mobility', 'Mobilidade'
        FUNCTIONAL = 'functional', 'Funcional'

    # CASCADE, não PROTECT: grupo muscular é dado pessoal (não catálogo global como
    # TipoExame em `saude`), e um grupo só existe para organizar os próprios exercícios da
    # pessoa. PROTECT aqui travaria a exclusão do grupo com erro sempre que ele tivesse
    # algum exercício — e travaria a futura exclusão de conta (LGPD) em cascata a partir de
    # User, porque o coletor do Django encontraria o vínculo protegido antes de saber que o
    # próprio Exercise também seria apagado na mesma operação.
    muscle_group = models.ForeignKey(
        MuscleGroup, on_delete=models.CASCADE, related_name='exercises', verbose_name='grupo muscular',
    )
    name = models.CharField('nome', max_length=140)
    type = models.CharField('tipo', max_length=12, choices=Type.choices, default=Type.STRENGTH)
    notes = models.TextField('observações', blank=True)

    class Meta:
        verbose_name = 'exercício'
        verbose_name_plural = 'exercícios'
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('treino:exercise_detail', args=[self.pk])


class WorkoutRoutine(OwnedModel):
    """A named plan — 'Push Pull Legs' — made of one or more days."""

    name = models.CharField('nome', max_length=140)
    description = models.TextField('descrição', blank=True)
    is_active = models.BooleanField('ativa', default=True)

    class Meta:
        verbose_name = 'ficha'
        verbose_name_plural = 'fichas'
        ordering = ['-is_active', 'name']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('treino:routine_detail', args=[self.pk])


class RoutineDay(OwnedModel):
    """One split of the routine — A, B, Push, Pull... — with the muscle groups it hits."""

    routine = models.ForeignKey(
        WorkoutRoutine, on_delete=models.CASCADE, related_name='days', verbose_name='ficha',
    )
    label = models.CharField('rótulo', max_length=60, help_text='Ex.: A, B, Push, Pull, Legs.')
    muscle_groups = models.ManyToManyField(
        MuscleGroup, related_name='routine_days', blank=True, verbose_name='grupos musculares',
    )
    order = models.PositiveSmallIntegerField('ordem', default=1)

    class Meta:
        verbose_name = 'divisão da ficha'
        verbose_name_plural = 'divisões da ficha'
        ordering = ['routine', 'order']

    def __str__(self):
        return f'{self.routine.name} · {self.label}'

    def get_absolute_url(self):
        return reverse('treino:routine_day_detail', args=[self.pk])


class RoutineExerciseTarget(OwnedModel):
    """An exercise placed on a routine day, with the sets and reps it's meant to be done at."""

    routine_day = models.ForeignKey(
        RoutineDay, on_delete=models.CASCADE, related_name='exercise_targets', verbose_name='divisão',
    )
    # CASCADE, não PROTECT — ver o comentário em Exercise.muscle_group: a mesma
    # armadilha (bloquear a exclusão em cascata do próprio dono) se repete aqui.
    exercise = models.ForeignKey(
        Exercise, on_delete=models.CASCADE, related_name='routine_targets', verbose_name='exercício',
    )
    target_sets = models.PositiveSmallIntegerField('séries alvo', default=3)
    target_reps = models.CharField('repetições alvo', max_length=20, default='10', help_text="Ex.: 10, 8-12, até a falha.")
    # O descanso é prescrição, não execução: pertence ao alvo, e não ao ``SessionEntry``,
    # que guarda o descanso realmente praticado naquele dia.
    rest_seconds = models.PositiveSmallIntegerField(
        'descanso (s)', null=True, blank=True, help_text='Ex.: 90. Arma o cronômetro da tela de registro.',
    )
    order = models.PositiveSmallIntegerField('ordem', default=1)

    class Meta:
        verbose_name = 'exercício da divisão'
        verbose_name_plural = 'exercícios da divisão'
        ordering = ['routine_day', 'order']
        constraints = [
            models.UniqueConstraint(
                fields=['routine_day', 'exercise'], name='exercicio_unico_por_divisao',
            )
        ]

    def __str__(self):
        return f'{self.exercise} · {self.target_sets}x{self.target_reps}'


class WorkoutSession(OwnedModel):
    """A day the person actually trained, optionally following a routine day."""

    class MorningAfter(models.TextChoices):
        OK = 'ok', 'Igual ou melhor'
        WORSE = 'worse', 'Pior que o normal'

    routine_day = models.ForeignKey(
        RoutineDay, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sessions', verbose_name='divisão seguida',
    )
    date = models.DateField('data', default=timezone.localdate)
    duration_minutes = models.PositiveSmallIntegerField('duração (min)', null=True, blank=True)
    # Numa tendinopatia a dor aparece no dia seguinte, não durante: é a manhã seguinte que
    # diz se a carga estava certa. Fica em coluna própria — e não em ``notes`` — porque é
    # dado consultado (contagem de semanas limpas), não texto livre.
    morning_after = models.CharField(
        'manhã seguinte', max_length=8, choices=MorningAfter.choices, blank=True,
        help_text='Como o corpo amanheceu no dia seguinte a este treino.',
    )
    notes = models.TextField('anotações', blank=True)

    class Meta:
        verbose_name = 'sessão de treino'
        verbose_name_plural = 'sessões de treino'
        ordering = ['-date']
        indexes = [models.Index(fields=['user', '-date'])]

    def __str__(self):
        return f'Treino de {self.date:%d/%m/%Y}'

    def get_absolute_url(self):
        return reverse('treino:session_detail', args=[self.pk])


class SessionEntry(OwnedModel):
    """One exercise performed within a session. The sets themselves live in ``SetLog``."""

    session = models.ForeignKey(
        WorkoutSession, on_delete=models.CASCADE, related_name='entries', verbose_name='sessão',
    )
    # CASCADE, não PROTECT — mesma razão: excluir um exercício apaga o próprio histórico
    # de séries dele, decisão do dono dos dados, e não pode travar em cadeia com PROTECT.
    exercise = models.ForeignKey(
        Exercise, on_delete=models.CASCADE, related_name='entries', verbose_name='exercício',
    )
    rest_seconds = models.PositiveSmallIntegerField('descanso (s)', null=True, blank=True)
    notes = models.CharField('observação', max_length=200, blank=True)
    order = models.PositiveSmallIntegerField('ordem', default=1)

    class Meta:
        verbose_name = 'exercício da sessão'
        verbose_name_plural = 'exercícios da sessão'
        ordering = ['session', 'order']

    def __str__(self):
        return f'{self.exercise} · {self.session.date:%d/%m/%Y}'

    def get_absolute_url(self):
        return self.session.get_absolute_url()

    @property
    def top_weight(self):
        """The heaviest set logged for this entry — the number that tracks a PR."""
        return self.sets.aggregate(models.Max('weight'))['weight__max']

    @property
    def total_reps(self):
        return self.sets.aggregate(models.Sum('reps'))['reps__sum'] or 0


class SetLog(OwnedModel):
    """
    One individual set: its own reps and weight.

    Split out from ``SessionEntry`` on purpose — see ``DECISIONS.md`` D-018 — so that a
    drop set or a pyramid (different weight or reps per set) is recorded as it happened,
    and the load-evolution chart plots a real number instead of an average.
    """

    entry = models.ForeignKey(SessionEntry, on_delete=models.CASCADE, related_name='sets', verbose_name='exercício')
    set_number = models.PositiveSmallIntegerField('série nº')
    reps = models.PositiveSmallIntegerField('repetições', validators=[MinValueValidator(1)])
    weight = models.DecimalField('carga (kg)', max_digits=6, decimal_places=2, default=0)

    class Meta:
        verbose_name = 'série'
        verbose_name_plural = 'séries'
        ordering = ['entry', 'set_number']
        constraints = [
            models.UniqueConstraint(fields=['entry', 'set_number'], name='numero_unico_por_entrada'),
        ]

    def __str__(self):
        return f'Série {self.set_number}: {self.reps}x{self.weight}kg'


def week_bounds(reference=None):
    """Monday through Sunday of the week containing ``reference`` (today by default)."""
    reference = reference or timezone.localdate()
    monday = reference - timedelta(days=reference.weekday())
    return monday, monday + timedelta(days=6)
