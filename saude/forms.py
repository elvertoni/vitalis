"""Health forms. Styling comes from the same Soluna widget classes used in accounts."""

import re

from django import forms

from accounts.forms import TEXT_INPUT_CLASS, StyledFormMixin

from .models import WEEKDAY_CHOICES, Appointment, Doctor, Exam, Medication, Treatment

TIME_PATTERN = re.compile(r'^([01]\d|2[0-3]):([0-5]\d)$')


class DateInput(forms.DateInput):
    input_type = 'date'

    def __init__(self, attrs=None):
        super().__init__(attrs={'class': TEXT_INPUT_CLASS, **(attrs or {})}, format='%Y-%m-%d')


class ScheduleTimesField(forms.CharField):
    """
    Reads ``08:00, 20:00`` from a text input and stores it as a list of strings.

    A plain text field beats a formset here: people type the times of a prescription in
    one go, and the model only ever needs them ordered and validated.
    """

    def __init__(self, **kwargs):
        kwargs.setdefault('required', False)
        kwargs.setdefault('label', 'Horários')
        kwargs.setdefault('help_text', 'Separados por vírgula, no formato 24h. Ex.: 08:00, 20:00.')
        kwargs.setdefault('widget', forms.TextInput(attrs={'class': TEXT_INPUT_CLASS, 'placeholder': '08:00, 20:00'}))
        super().__init__(**kwargs)

    def prepare_value(self, value):
        if isinstance(value, list):
            return ', '.join(value)
        return value

    def clean(self, value):
        value = super().clean(value)
        if not value:
            return []
        times = []
        for chunk in value.split(','):
            candidate = chunk.strip()
            if not candidate:
                continue
            if not TIME_PATTERN.match(candidate):
                raise forms.ValidationError(f'"{candidate}" não é um horário válido. Use HH:MM.')
            times.append(candidate)
        return sorted(set(times))


class DoctorForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Doctor
        fields = ['name', 'specialty', 'phone', 'email', 'clinic_name', 'clinic_address', 'notes']
        widgets = {'notes': forms.Textarea(attrs={'rows': 4})}


class TreatmentForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Treatment
        fields = ['name', 'doctor', 'start_date', 'end_date', 'status', 'description', 'notes']
        widgets = {
            'start_date': DateInput(),
            'end_date': DateInput(),
            'description': forms.Textarea(attrs={'rows': 4}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }


class ExamForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Exam
        fields = [
            'name',
            'status',
            'doctor',
            'treatment',
            'requested_date',
            'scheduled_date',
            'done_date',
            'result_summary',
            'attachment',
        ]
        widgets = {
            'requested_date': DateInput(),
            'scheduled_date': DateInput(),
            'done_date': DateInput(),
            'result_summary': forms.Textarea(attrs={'rows': 5}),
        }

    def clean(self):
        cleaned = super().clean()
        done_date = cleaned.get('done_date')
        requested_date = cleaned.get('requested_date')
        if done_date and requested_date and done_date < requested_date:
            self.add_error('done_date', 'A data de realização não pode ser anterior à solicitação.')
        # Keeps the status honest: a filled result date means the exam happened.
        if done_date and cleaned.get('status') != Exam.Status.DONE:
            cleaned['status'] = Exam.Status.DONE
        return cleaned


class AppointmentForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ['doctor', 'treatment', 'date', 'reason', 'notes', 'next_return_date']
        widgets = {
            'date': DateInput(),
            'next_return_date': DateInput(),
            'notes': forms.Textarea(attrs={'rows': 5}),
        }

    def clean(self):
        cleaned = super().clean()
        date = cleaned.get('date')
        next_return_date = cleaned.get('next_return_date')
        if date and next_return_date and next_return_date <= date:
            self.add_error('next_return_date', 'O retorno precisa ser depois da consulta.')
        return cleaned


class WeekdayChips(forms.CheckboxSelectMultiple):
    """
    As sete caixas viram pastilhas lado a lado — sete linhas empilhadas afogam o formulário.

    O template vive dentro da app, e não em ``templates/`` como todo o resto: o renderizador
    de formulários do Django usa um motor próprio, que enxerga as pastas de template das apps
    mas **não** a pasta do projeto. Colocado lá fora, o widget quebra com ``TemplateDoesNotExist``.
    """

    template_name = 'saude/widgets/weekday_chips.html'


class WeekdaysField(forms.TypedMultipleChoiceField):
    """
    Os dias da semana em que o remédio é tomado, como caixas de marcar.

    Nada marcado significa **todo dia**, não "nenhum dia": é o caso da maioria das receitas,
    e obrigar a marcar os sete daria trabalho para dizer o que já é o padrão.
    """

    def __init__(self, **kwargs):
        kwargs.setdefault('required', False)
        kwargs.setdefault('label', 'Dias da semana')
        kwargs.setdefault('help_text', 'Deixe em branco para todo dia. Marque só os dias de remédio semanal.')
        kwargs.setdefault('choices', WEEKDAY_CHOICES)
        kwargs.setdefault('coerce', int)
        kwargs.setdefault('widget', WeekdayChips())
        super().__init__(**kwargs)

    def clean(self, value):
        return sorted(super().clean(value) or [])


class MedicationForm(StyledFormMixin, forms.ModelForm):
    schedule_times = ScheduleTimesField()
    weekdays = WeekdaysField()

    class Meta:
        model = Medication
        fields = [
            'name',
            'dosage',
            'frequency',
            'treatment',
            'start_date',
            'end_date',
            'schedule_times',
            'weekdays',
            'cycle_daily_days',
            'cycle_alternates_after',
            'is_active',
        ]
        widgets = {'start_date': DateInput(), 'end_date': DateInput()}

    def clean(self):
        cleaned = super().clean()
        start_date = cleaned.get('start_date')
        end_date = cleaned.get('end_date')
        if start_date and end_date and end_date < start_date:
            self.add_error('end_date', 'O término não pode ser antes do início.')
        # Marcar o dia sem marcar a hora não gera lembrete nenhum: o gerador percorre os
        # horários. Melhor barrar aqui do que deixar o remédio semanal em silêncio.
        if cleaned.get('weekdays') and not cleaned.get('schedule_times'):
            self.add_error(
                'schedule_times',
                'Informe ao menos um horário para o lembrete do dia marcado sair.',
            )
        return cleaned
