"""Training forms. Widgets follow the same Soluna classes used across the app."""

from django import forms

from accounts.forms import StyledFormMixin

from .models import (
    Exercise,
    MuscleGroup,
    RoutineDay,
    RoutineExerciseTarget,
    SessionEntry,
    SetLog,
    WorkoutRoutine,
    WorkoutSession,
)


class DateInput(forms.DateInput):
    input_type = 'date'

    def __init__(self, attrs=None):
        from accounts.forms import TEXT_INPUT_CLASS

        super().__init__(attrs={'class': TEXT_INPUT_CLASS, **(attrs or {})}, format='%Y-%m-%d')


class MuscleGroupForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = MuscleGroup
        fields = ['name']


class ExerciseForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Exercise
        fields = ['name', 'muscle_group', 'type', 'notes']
        widgets = {'notes': forms.Textarea(attrs={'rows': 3})}


class WorkoutRoutineForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = WorkoutRoutine
        fields = ['name', 'description', 'is_active']
        widgets = {'description': forms.Textarea(attrs={'rows': 3})}


class RoutineDayForm(StyledFormMixin, forms.ModelForm):
    """``routine`` is stamped by the view from the URL, not offered here."""

    class Meta:
        model = RoutineDay
        fields = ['label', 'muscle_groups', 'order']
        widgets = {'muscle_groups': forms.SelectMultiple}


class RoutineExerciseTargetForm(StyledFormMixin, forms.ModelForm):
    """``routine_day`` is stamped by the view from the URL, not offered here."""

    class Meta:
        model = RoutineExerciseTarget
        fields = ['exercise', 'target_sets', 'target_reps', 'rest_seconds', 'order']


class WorkoutSessionForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = WorkoutSession
        fields = ['routine_day', 'date', 'duration_minutes', 'morning_after', 'notes']
        widgets = {'date': DateInput(), 'notes': forms.Textarea(attrs={'rows': 3})}


class SessionEntryForm(StyledFormMixin, forms.ModelForm):
    """``session`` is stamped by the view from the URL, not offered here."""

    class Meta:
        model = SessionEntry
        fields = ['exercise', 'rest_seconds', 'notes', 'order']


class SetLogForm(StyledFormMixin, forms.ModelForm):
    """``entry`` is stamped by the view from the URL, not offered here."""

    class Meta:
        model = SetLog
        fields = ['set_number', 'reps', 'weight']
