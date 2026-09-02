"""
Nutrition domain: a food bank, meal plans, what was actually eaten, and body weight.

Every model here is personal — including ``Meal`` and ``MealItem``, nested under ``Diet`` —
so every one of them inherits from ``OwnedModel``. See ``DECISIONS.md`` D-019 for why the
child models carry their own ``user`` column instead of relying only on the parent chain.
"""

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

from core.models import OwnedModel


class Food(OwnedModel):
    """
    A food in the person's own bank, with macros per a base portion (usually 100 g).

    Personal, not a shared catalog like ``saude.TipoExame`` — see D-021: a shared catalog
    earns ``PROTECT``, personal data never does. Deleting a food cascades into whatever meals
    and logs used it.
    """

    name = models.CharField('nome', max_length=140)
    portion_base_g = models.PositiveSmallIntegerField('porção base (g)', default=100)
    calories = models.DecimalField('calorias (kcal)', max_digits=7, decimal_places=2)
    protein_g = models.DecimalField('proteína (g)', max_digits=6, decimal_places=2, default=0)
    carbs_g = models.DecimalField('carboidrato (g)', max_digits=6, decimal_places=2, default=0)
    fat_g = models.DecimalField('gordura (g)', max_digits=6, decimal_places=2, default=0)

    class Meta:
        verbose_name = 'alimento'
        verbose_name_plural = 'alimentos'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['user', 'name'], name='alimento_unico_por_usuario'),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('nutricao:food_detail', args=[self.pk])

    def macros_for(self, quantity_g):
        """Macros scaled from the base portion to an arbitrary quantity."""
        if not self.portion_base_g:
            return Macros.zero()
        factor = Decimal(quantity_g) / Decimal(self.portion_base_g)
        return Macros(
            calories=self.calories * factor,
            protein_g=self.protein_g * factor,
            carbs_g=self.carbs_g * factor,
            fat_g=self.fat_g * factor,
        )


class Macros:
    """A calories + protein/carbs/fat bundle. Not a model — just the shape every total takes."""

    __slots__ = ('calories', 'protein_g', 'carbs_g', 'fat_g')

    def __init__(self, calories=0, protein_g=0, carbs_g=0, fat_g=0):
        self.calories = calories or Decimal('0')
        self.protein_g = protein_g or Decimal('0')
        self.carbs_g = carbs_g or Decimal('0')
        self.fat_g = fat_g or Decimal('0')

    @classmethod
    def zero(cls):
        return cls()

    def __add__(self, other):
        return Macros(
            self.calories + other.calories,
            self.protein_g + other.protein_g,
            self.carbs_g + other.carbs_g,
            self.fat_g + other.fat_g,
        )

    def __repr__(self):
        return f'Macros(kcal={self.calories}, p={self.protein_g}, c={self.carbs_g}, f={self.fat_g})'


class Diet(OwnedModel):
    """A meal plan: a daily calorie/macro target, broken into meals."""

    class Goal(models.TextChoices):
        WEIGHT_LOSS = 'weight_loss', 'Emagrecimento'
        MAINTENANCE = 'maintenance', 'Manutenção'
        WEIGHT_GAIN = 'weight_gain', 'Ganho de massa'

    name = models.CharField('nome', max_length=140)
    goal = models.CharField('objetivo', max_length=12, choices=Goal.choices, default=Goal.MAINTENANCE)
    daily_calorie_target = models.PositiveIntegerField('meta de calorias (kcal)', null=True, blank=True)
    protein_target_g = models.PositiveSmallIntegerField('meta de proteína (g)', null=True, blank=True)
    carbs_target_g = models.PositiveSmallIntegerField('meta de carboidrato (g)', null=True, blank=True)
    fat_target_g = models.PositiveSmallIntegerField('meta de gordura (g)', null=True, blank=True)
    is_active = models.BooleanField('ativa', default=True)

    class Meta:
        verbose_name = 'dieta'
        verbose_name_plural = 'dietas'
        ordering = ['-is_active', 'name']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('nutricao:diet_detail', args=[self.pk])

    @property
    def target_macros(self):
        return Macros(
            calories=self.daily_calorie_target or 0,
            protein_g=self.protein_target_g or 0,
            carbs_g=self.carbs_target_g or 0,
            fat_g=self.fat_target_g or 0,
        )

    @property
    def planned_macros(self):
        """Sum of every meal's macros — what the plan adds up to on paper."""
        total = Macros.zero()
        for meal in self.meals.all():
            total = total + meal.macros
        return total


class Meal(OwnedModel):
    """A slot in the plan — breakfast, lunch — with the foods it's made of."""

    diet = models.ForeignKey(Diet, on_delete=models.CASCADE, related_name='meals', verbose_name='dieta')
    name = models.CharField('nome', max_length=80, help_text='Ex.: café da manhã, almoço, lanche.')
    time = models.TimeField('horário sugerido', null=True, blank=True)
    description = models.CharField(
        'descrição',
        max_length=240,
        blank=True,
        help_text='Como a refeição é montada, em uma linha. Ex.: 25 g de tapioca · 3 ovos.',
    )
    change_note = models.CharField(
        'o que mudou',
        max_length=180,
        blank=True,
        help_text='O que essa refeição ganhou em relação ao plano anterior. Aparece no comparador.',
    )
    order = models.PositiveSmallIntegerField('ordem', default=1)

    class Meta:
        verbose_name = 'refeição'
        verbose_name_plural = 'refeições'
        ordering = ['diet', 'order', 'time']

    def __str__(self):
        return f'{self.name} · {self.diet.name}'

    def get_absolute_url(self):
        return reverse('nutricao:meal_detail', args=[self.pk])

    @property
    def macros(self):
        total = Macros.zero()
        for item in self.items.select_related('food').all():
            total = total + item.macros
        return total


class MealItem(OwnedModel):
    """A food and a quantity inside a meal. Macros are computed live, never stored."""

    meal = models.ForeignKey(Meal, on_delete=models.CASCADE, related_name='items', verbose_name='refeição')
    food = models.ForeignKey(Food, on_delete=models.CASCADE, related_name='meal_items', verbose_name='alimento')
    quantity_g = models.DecimalField('quantidade (g)', max_digits=6, decimal_places=1, validators=[MinValueValidator(Decimal('0.1'))])

    class Meta:
        verbose_name = 'item da refeição'
        verbose_name_plural = 'itens da refeição'
        ordering = ['meal', 'id']

    def __str__(self):
        return f'{self.food.name} · {self.quantity_g}g'

    @property
    def macros(self):
        return self.food.macros_for(self.quantity_g)


class DailyLog(OwnedModel):
    """
    What was actually eaten on a given day — independent of any ``Diet``/``Meal`` structure.

    ``meal_name`` is free text on purpose (breakfast, lunch, a snack at 4pm): the plan's
    ``Meal`` is a template for what's *supposed* to happen, this is what *did*.
    """

    date = models.DateField('data', default=timezone.localdate)
    meal_name = models.CharField('refeição', max_length=80, help_text='Ex.: café da manhã, almoço, lanche.')
    food = models.ForeignKey(Food, on_delete=models.CASCADE, related_name='daily_logs', verbose_name='alimento')
    quantity_g = models.DecimalField('quantidade (g)', max_digits=6, decimal_places=1, validators=[MinValueValidator(Decimal('0.1'))])

    class Meta:
        verbose_name = 'registro diário'
        verbose_name_plural = 'registros diários'
        ordering = ['-date', 'id']
        indexes = [models.Index(fields=['user', '-date'])]

    def __str__(self):
        return f'{self.food.name} · {self.quantity_g}g · {self.date:%d/%m/%Y}'

    @property
    def macros(self):
        return self.food.macros_for(self.quantity_g)


class WeightLog(OwnedModel):
    """One body-weight reading. The line the evolution chart plots."""

    date = models.DateField('data', default=timezone.localdate)
    weight_kg = models.DecimalField('peso (kg)', max_digits=5, decimal_places=2)
    notes = models.CharField('observação', max_length=200, blank=True)

    class Meta:
        verbose_name = 'registro de peso'
        verbose_name_plural = 'registros de peso'
        ordering = ['-date']
        constraints = [
            models.UniqueConstraint(fields=['user', 'date'], name='um_peso_por_dia'),
        ]

    def __str__(self):
        return f'{self.weight_kg} kg · {self.date:%d/%m/%Y}'


def daily_totals(user, date):
    """Sum of macros logged by ``user`` on ``date`` — the actual side of 'consumido x planejado'."""
    total = Macros.zero()
    for log in DailyLog.objects.filter(user=user, date=date).select_related('food'):
        total = total + log.macros
    return total


def estimate_daily_calories(profile, weight_kg, goal):
    """
    Mifflin-St Jeor BMR × a light activity factor, adjusted by goal — the optional
    suggestion from PRD 8.2. Returns ``None`` when the inputs needed (age, height, sex,
    a recent weight) are not on file; the person always overrides it by hand regardless.
    """
    if not (profile.birth_date and profile.height_cm and profile.sex and weight_kg):
        return None
    age = profile.age
    weight = float(weight_kg)
    height = float(profile.height_cm)
    if profile.sex == profile.Sex.MALE:
        bmr = 10 * weight + 6.25 * height - 5 * age + 5
    elif profile.sex == profile.Sex.FEMALE:
        bmr = 10 * weight + 6.25 * height - 5 * age - 161
    else:
        bmr = 10 * weight + 6.25 * height - 5 * age - 78  # média dos dois ajustes
    maintenance = bmr * 1.375  # atividade leve — sedentário a moderado
    adjustment = {'weight_loss': 0.85, 'maintenance': 1.0, 'weight_gain': 1.15}.get(goal, 1.0)
    return round(maintenance * adjustment)
