"""
Reading of the plans and of body composition — pure calculation, no view and no writing.

Two things live here. ``bmi_snapshot`` turns the height on the profile and the last weighing
into the number and the position of the BMI ruler. ``plan_comparison`` reads two of the
person's own diets — the active one and the one before it — as the two sides of the menu
comparator.

Nothing here holds a value of its own: a screen that shows no comparison is a person with
fewer than two diets on file, not a bug.
"""

from .models import Diet, WeightLog, estimate_daily_calories

# Faixas da OMS. O topo da régua é 40: acima disso a barra deixa de discriminar e o ponto
# encosta no fim de qualquer jeito.
BMI_SCALE_MIN = 15.0
BMI_SCALE_MAX = 40.0
BMI_BANDS = (
    (18.5, 'Abaixo do peso'),
    (25.0, 'Peso normal'),
    (30.0, 'Sobrepeso'),
    (35.0, 'Obesidade grau I'),
    (40.0, 'Obesidade grau II'),
)
BMI_ABOVE_BANDS = 'Obesidade grau III'

# Déficit diário a partir do qual a perda deixa de ser segura sem acompanhamento: acima disso
# a massa magra vai junto. Serve para rotular o comparador, não para proibir nada.
SAFE_DEFICIT_KCAL = 1000


def bmi_snapshot(profile, weight_kg):
    """
    BMI, its position on the drawn ruler and the band it falls in.

    Returns ``None`` when height or weight is missing — the screen then simply omits the card
    instead of showing a number built on a guess.
    """
    if not (profile and profile.height_cm and weight_kg):
        return None

    height_m = float(profile.height_cm) / 100.0
    weight = float(weight_kg)
    bmi = weight / (height_m ** 2)

    span = BMI_SCALE_MAX - BMI_SCALE_MIN
    position = max(0.0, min(100.0, ((bmi - BMI_SCALE_MIN) / span) * 100.0))

    label = BMI_ABOVE_BANDS
    for ceiling, name in BMI_BANDS:
        if bmi < ceiling:
            label = name
            break

    return {
        'value': round(bmi, 1),
        'position': position,
        'label': label,
        'weight_kg': weight,
        'height_m': height_m,
        'is_healthy': 18.5 <= bmi < 25.0,
    }


def latest_weight(user):
    """The last weighing on file — the single source of the current weight (D-047)."""
    log = WeightLog.objects.filter(user=user).order_by('-date').first()
    return log.weight_kg if log else None


def _plan_summary(diet, reference_weight_kg, maintenance_kcal):
    """
    One side of the comparator: what the plan adds up to, and what that means.

    Every number leaves as ``int``/``float`` and never as ``Decimal``: the comparator ships
    this dict to the browser through ``json_script``, and a ``Decimal`` would arrive there as
    a string that no longer knows how to be formatted or compared.
    """
    planned = diet.planned_macros
    calories = float(planned.calories or diet.daily_calorie_target or 0)
    protein = float(planned.protein_g or diet.protein_target_g or 0)
    weight = float(reference_weight_kg) if reference_weight_kg else None

    deficit = None
    within_safe_deficit = None
    if maintenance_kcal and calories:
        deficit = round(maintenance_kcal - calories)
        within_safe_deficit = deficit <= SAFE_DEFICIT_KCAL

    return {
        'pk': diet.pk,
        'name': diet.name,
        'goal': diet.get_goal_display(),
        'is_active': diet.is_active,
        'calories': round(calories),
        'protein_g': round(protein),
        'protein_per_kg': round(protein / weight, 2) if weight and protein else None,
        'deficit': deficit,
        'within_safe_deficit': within_safe_deficit,
        'meals': [
            {
                'time': meal.time.strftime('%H:%M') if meal.time else '',
                'name': meal.name,
                'description': meal.description,
                'change_note': meal.change_note,
                'calories': round(float(meal.macros.calories)),
                'protein_g': round(float(meal.macros.protein_g), 1),
            }
            for meal in diet.meals.all()
        ],
    }


def plan_comparison(user, profile=None, weight_kg=None):
    """
    The active diet against the one before it, both read from the person's own rows.

    Returns ``None`` with fewer than two diets on file: there is nothing to compare, and an
    empty comparator is worse than no comparator. The maintenance estimate behind the deficit
    is the same Mifflin-St Jeor used by the diet form, so both screens agree.
    """
    diets = list(
        Diet.objects.filter(user=user)
        .order_by('-is_active', '-updated_at')
        .prefetch_related('meals__items__food')[:2]
    )
    if len(diets) < 2:
        return None

    current, previous = diets[0], diets[1]
    if weight_kg is None:
        weight_kg = latest_weight(user)
    maintenance = None
    target_weight = getattr(profile, 'target_weight_kg', None) if profile else None
    if profile is not None:
        maintenance = estimate_daily_calories(profile, weight_kg, Diet.Goal.MAINTENANCE)

    # A proteína por quilo se lê sobre o peso alvo quando ele existe: em quem está acima do
    # peso, dividir pela massa atual pede proteína para gordura que a pessoa está perdendo.
    reference_weight = target_weight or weight_kg

    return {
        'current': _plan_summary(current, reference_weight, maintenance),
        'previous': _plan_summary(previous, reference_weight, maintenance),
        'maintenance_kcal': maintenance,
        'safe_deficit_kcal': SAFE_DEFICIT_KCAL,
        'reference_weight_kg': float(reference_weight) if reference_weight else None,
        'reference_is_target': bool(target_weight),
    }


__all__ = [
    'BMI_SCALE_MAX',
    'BMI_SCALE_MIN',
    'SAFE_DEFICIT_KCAL',
    'bmi_snapshot',
    'latest_weight',
    'plan_comparison',
]
