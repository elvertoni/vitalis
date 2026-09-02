"""
Health views. Every one of them is owner scoped through the bases in ``core.views``.

The attachment download deserves the extra attention: it is the only route here that
hands back a file, and a report is the most sensitive thing the system stores.
"""

from datetime import timedelta
from pathlib import Path

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from core.views import (
    OwnerCreateView,
    OwnerDeleteView,
    OwnerDetailView,
    OwnerListView,
    OwnerUpdateView,
)

from .forms import AppointmentForm, DoctorForm, ExamForm, MedicationForm, TreatmentForm
from .models import Appointment, Doctor, Exam, Medication, Treatment


class HealthIndexView(LoginRequiredMixin, TemplateView):
    """Hub of the health area, with the counters of each section."""

    template_name = 'saude/index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        today = timezone.localdate()
        context['doctor_count'] = Doctor.objects.filter(user=user).count()
        context['treatment_count'] = Treatment.objects.filter(
            user=user, status__in=[Treatment.Status.ONGOING, Treatment.Status.PAUSED]
        ).count()
        context['exam_count'] = Exam.objects.filter(user=user).count()
        context['appointment_count'] = Appointment.objects.filter(user=user).count()
        context['medication_count'] = Medication.objects.filter(user=user, is_active=True).count()
        context['upcoming'] = (
            Appointment.objects.filter(
                user=user,
                next_return_date__gte=today,
                next_return_date__lte=today + timedelta(days=60),
            )
            .select_related('doctor')
            .order_by('next_return_date')[:5]
        )
        return context


# ── Médicos ──────────────────────────────────────────────────────────────────


class DoctorListView(OwnerListView):
    model = Doctor
    template_name = 'saude/doctor_list.html'


class DoctorDetailView(OwnerDetailView):
    model = Doctor
    template_name = 'saude/doctor_detail.html'


class DoctorCreateView(OwnerCreateView):
    model = Doctor
    form_class = DoctorForm
    template_name = 'saude/object_form.html'
    success_message = 'Médico cadastrado.'
    extra_context = {'page_kicker': 'Médicos', 'page_title': 'Novo médico'}


class DoctorUpdateView(OwnerUpdateView):
    model = Doctor
    form_class = DoctorForm
    template_name = 'saude/object_form.html'
    extra_context = {'page_kicker': 'Médicos', 'page_title': 'Editar médico'}


class DoctorDeleteView(OwnerDeleteView):
    model = Doctor
    success_url = reverse_lazy('saude:doctor_list')
    success_message = 'Médico excluído.'


# ── Tratamentos ──────────────────────────────────────────────────────────────


class TreatmentListView(OwnerListView):
    model = Treatment
    template_name = 'saude/treatment_list.html'

    def get_queryset(self):
        return super().get_queryset().select_related('doctor')


class TreatmentDetailView(OwnerDetailView):
    model = Treatment
    template_name = 'saude/treatment_detail.html'

    def get_queryset(self):
        return super().get_queryset().select_related('doctor')


class TreatmentCreateView(OwnerCreateView):
    model = Treatment
    form_class = TreatmentForm
    template_name = 'saude/object_form.html'
    success_message = 'Tratamento criado.'
    extra_context = {'page_kicker': 'Tratamentos', 'page_title': 'Novo tratamento'}


class TreatmentUpdateView(OwnerUpdateView):
    model = Treatment
    form_class = TreatmentForm
    template_name = 'saude/object_form.html'
    extra_context = {'page_kicker': 'Tratamentos', 'page_title': 'Editar tratamento'}


class TreatmentDeleteView(OwnerDeleteView):
    model = Treatment
    success_url = reverse_lazy('saude:treatment_list')
    success_message = 'Tratamento excluído.'


# ── Exames ───────────────────────────────────────────────────────────────────


class ExamListView(OwnerListView):
    model = Exam
    template_name = 'saude/exam_list.html'

    def get_queryset(self):
        return super().get_queryset().select_related('doctor', 'treatment')


class ExamDetailView(OwnerDetailView):
    model = Exam
    template_name = 'saude/exam_detail.html'

    def get_queryset(self):
        return super().get_queryset().select_related('doctor', 'treatment')


class ExamCreateView(OwnerCreateView):
    model = Exam
    form_class = ExamForm
    template_name = 'saude/object_form.html'
    success_message = 'Exame registrado.'
    extra_context = {'page_kicker': 'Exames', 'page_title': 'Novo exame'}


class ExamUpdateView(OwnerUpdateView):
    model = Exam
    form_class = ExamForm
    template_name = 'saude/object_form.html'
    extra_context = {'page_kicker': 'Exames', 'page_title': 'Editar exame'}


class ExamDeleteView(OwnerDeleteView):
    model = Exam
    success_url = reverse_lazy('saude:exam_list')
    success_message = 'Exame excluído.'


class ExamAttachmentView(LoginRequiredMixin, View):
    """
    Serves the report of an exam the requester owns.

    The file is never reachable by a direct media URL: the stored name is random, and
    this view is the only door. Someone else's exam id returns 404 — the same answer as
    an id that does not exist, so the response does not confirm that the exam is real.
    """

    def get(self, request, pk):
        exam = get_object_or_404(Exam, pk=pk, user=request.user)
        if not exam.attachment:
            raise Http404('Este exame não tem laudo anexado.')
        ext = Path(exam.attachment.name).suffix or '.pdf'
        clean_name = exam.name.replace('/', '-').replace('\\', '-')
        return FileResponse(exam.attachment.open('rb'), filename=f'{clean_name}{ext}')


# ── Consultas ────────────────────────────────────────────────────────────────


class AppointmentListView(OwnerListView):
    model = Appointment
    template_name = 'saude/appointment_list.html'

    def get_queryset(self):
        return super().get_queryset().select_related('doctor', 'treatment')


class AppointmentDetailView(OwnerDetailView):
    model = Appointment
    template_name = 'saude/appointment_detail.html'

    def get_queryset(self):
        return super().get_queryset().select_related('doctor', 'treatment')


class AppointmentCreateView(OwnerCreateView):
    model = Appointment
    form_class = AppointmentForm
    template_name = 'saude/object_form.html'
    success_message = 'Consulta registrada.'
    extra_context = {'page_kicker': 'Consultas', 'page_title': 'Nova consulta'}


class AppointmentUpdateView(OwnerUpdateView):
    model = Appointment
    form_class = AppointmentForm
    template_name = 'saude/object_form.html'
    extra_context = {'page_kicker': 'Consultas', 'page_title': 'Editar consulta'}


class AppointmentDeleteView(OwnerDeleteView):
    model = Appointment
    success_url = reverse_lazy('saude:appointment_list')
    success_message = 'Consulta excluída.'


# ── Medicamentos ─────────────────────────────────────────────────────────────


class MedicationListView(OwnerListView):
    model = Medication
    template_name = 'saude/medication_list.html'

    def get_queryset(self):
        return super().get_queryset().select_related('treatment')


class MedicationDetailView(OwnerDetailView):
    model = Medication
    template_name = 'saude/medication_detail.html'

    def get_queryset(self):
        return super().get_queryset().select_related('treatment')


class MedicationCreateView(OwnerCreateView):
    model = Medication
    form_class = MedicationForm
    template_name = 'saude/object_form.html'
    success_message = 'Medicamento cadastrado.'
    extra_context = {'page_kicker': 'Medicamentos', 'page_title': 'Novo medicamento'}


class MedicationUpdateView(OwnerUpdateView):
    model = Medication
    form_class = MedicationForm
    template_name = 'saude/object_form.html'
    extra_context = {'page_kicker': 'Medicamentos', 'page_title': 'Editar medicamento'}


class MedicationDeleteView(OwnerDeleteView):
    model = Medication
    success_url = reverse_lazy('saude:medication_list')
    success_message = 'Medicamento excluído.'
