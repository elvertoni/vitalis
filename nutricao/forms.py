"""Nutrition forms. Same Soluna widget classes as the rest of the app."""

from django import forms

from accounts.forms import TEXT_INPUT_CLASS, StyledFormMixin

from .models import DailyLog, Diet, Food, Meal, MealItem, WeightLog


class DateInput(forms.DateInput):
    input_type = 'date'

    def __init__(self, attrs=None):
        super().__init__(attrs={'class': TEXT_INPUT_CLASS, **(attrs or {})}, format='%Y-%m-%d')


class TimeInput(forms.TimeInput):
    input_type = 'time'

    def __init__(self, attrs=None):
        super().__init__(attrs={'class': TEXT_INPUT_CLASS, **(attrs or {})}, format='%H:%M')


class FoodForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Food
        fields = ['name', 'portion_base_g', 'calories', 'protein_g', 'carbs_g', 'fat_g']


class DietForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Diet
        fields = [
            'name', 'goal', 'is_active',
            'daily_calorie_target', 'protein_target_g', 'carbs_target_g', 'fat_target_g',
        ]


class MealForm(StyledFormMixin, forms.ModelForm):
    """``diet`` is stamped by the view from the URL, not offered here."""

    class Meta:
        model = Meal
        fields = ['name', 'time', 'order']
        widgets = {'time': TimeInput()}


class MealItemForm(StyledFormMixin, forms.ModelForm):
    """``meal`` is stamped by the view from the URL, not offered here."""

    class Meta:
        model = MealItem
        fields = ['food', 'quantity_g']


class DailyLogForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = DailyLog
        fields = ['date', 'meal_name', 'food', 'quantity_g']
        widgets = {'date': DateInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['meal_name'].widget.attrs['placeholder'] = 'Café da manhã, almoço, lanche...'


class WeightLogForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = WeightLog
        fields = ['date', 'weight_kg', 'notes']
        widgets = {'date': DateInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['weight_kg'].widget.attrs['placeholder'] = 'Ex.: 78.5'
