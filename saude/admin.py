from django.contrib import admin

from .models import (
    Appointment,
    ClinicalNote,
    Doctor,
    Exam,
    LabPanel,
    LabResult,
    Medication,
    Treatment,
)


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ['name', 'specialty', 'user', 'clinic_name']
    list_filter = ['specialty']
    search_fields = ['name', 'clinic_name', 'user__email']


@admin.register(Treatment)
class TreatmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'doctor', 'status', 'start_date', 'end_date']
    list_filter = ['status']
    search_fields = ['name', 'user__email']


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'status', 'requested_date', 'done_date']
    list_filter = ['status']
    search_fields = ['name', 'user__email']


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ['doctor', 'user', 'date', 'next_return_date']
    search_fields = ['doctor__name', 'user__email']


@admin.register(Medication)
class MedicationAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'dosage', 'is_active', 'start_date', 'end_date']
    list_filter = ['is_active']
    search_fields = ['name', 'user__email']


class LabResultInline(admin.TabularInline):
    model = LabResult
    extra = 0
    fields = ['order', 'name', 'unit', 'value', 'previous_value', 'ref_low', 'ref_high', 'scale_min', 'scale_max', 'status', 'decimals', 'note']


@admin.register(LabPanel)
class LabPanelAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'sample_kind', 'exam', 'order']
    list_filter = ['sample_kind']
    search_fields = ['title', 'user__email']
    inlines = [LabResultInline]


@admin.register(LabResult)
class LabResultAdmin(admin.ModelAdmin):
    list_display = ['name', 'panel', 'value', 'unit', 'status']
    list_filter = ['status']
    search_fields = ['name', 'user__email']


@admin.register(ClinicalNote)
class ClinicalNoteAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'kind', 'severity', 'order']
    list_filter = ['kind', 'severity']
    search_fields = ['title', 'user__email']
