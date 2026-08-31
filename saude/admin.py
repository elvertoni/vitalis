from django.contrib import admin

from .models import Appointment, Doctor, Exam, Medication, Treatment


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
