"""Treatment forms. Styling comes from the Soluna widget classes shared with accounts."""

from datetime import timedelta

from django import forms
from django.utils import timezone

from accounts.forms import TEXT_INPUT_CLASS, StyledFormMixin
from saude.forms import DateInput

from .models import Injection, SideEffect


class DateTimeInput(forms.DateTimeInput):
    input_type = 'datetime-local'

    def __init__(self, attrs=None):
        super().__init__(attrs={'class': TEXT_INPUT_CLASS, **(attrs or {})}, format='%Y-%m-%dT%H:%M')


class InjectionForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Injection
        fields = ['medication', 'applied_at', 'dose_mg', 'site', 'notes']
        widgets = {'applied_at': DateTimeInput()}

    def clean_applied_at(self):
        applied_at = self.cleaned_data['applied_at']
        # Registro é do que já aconteceu. Aplicação no futuro é quase sempre data errada
        # e faria a próxima dose sumir do card antes da hora.
        if applied_at > timezone.now() + timedelta(minutes=5):
            raise forms.ValidationError('A aplicação não pode estar no futuro.')
        return applied_at


class SideEffectForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = SideEffect
        fields = ['date', 'kind', 'intensity', 'injection', 'notes']
        widgets = {'date': DateInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # As aplicações mais recentes primeiro; o filtro por dono vem do OwnerFormMixin.
        self.fields['injection'].queryset = Injection.objects.select_related('medication').order_by('-applied_at')

    def clean_date(self):
        date = self.cleaned_data['date']
        if date > timezone.localdate():
            raise forms.ValidationError('A data não pode estar no futuro.')
        return date
