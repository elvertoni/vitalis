"""Form for a hand-typed reminder. Derived reminders are never edited through a form."""

from django import forms

from accounts.forms import TEXT_INPUT_CLASS, StyledFormMixin

from .models import Reminder


class DateTimeInput(forms.DateTimeInput):
    input_type = 'datetime-local'

    def __init__(self, attrs=None):
        super().__init__(attrs={'class': TEXT_INPUT_CLASS, **(attrs or {})}, format='%Y-%m-%dT%H:%M')


class ReminderForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Reminder
        fields = ['category', 'title', 'description', 'remind_at', 'is_recurring', 'recurrence_rule']
        widgets = {
            'remind_at': DateTimeInput(),
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['remind_at'].input_formats = ['%Y-%m-%dT%H:%M']
        self.fields['recurrence_rule'].widget.attrs['placeholder'] = 'Ex.: toda segunda às 08:00'
