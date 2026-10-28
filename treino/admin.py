from django.contrib import admin

from .models import (
    Exercise,
    ExerciseGuide,
    MuscleGroup,
    RoutineDay,
    RoutineExerciseTarget,
    SessionEntry,
    SetLog,
    WorkoutRoutine,
    WorkoutSession,
)


@admin.register(MuscleGroup)
class MuscleGroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'user']
    search_fields = ['name', 'user__email']


@admin.register(ExerciseGuide)
class ExerciseGuideAdmin(admin.ModelAdmin):
    """Só leitura: a fonte é treino/catalog/exercises.json, e o deploy sobrescreve o banco."""

    list_display = ['name', 'slug', 'equipment', 'has_illustration']
    list_filter = ['has_illustration']
    search_fields = ['name', 'slug']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    list_display = ['name', 'muscle_group', 'type', 'guide', 'user']
    list_filter = ['type']
    search_fields = ['name', 'user__email']


class RoutineDayInline(admin.TabularInline):
    model = RoutineDay
    extra = 0


@admin.register(WorkoutRoutine)
class WorkoutRoutineAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'user__email']
    inlines = [RoutineDayInline]


@admin.register(RoutineDay)
class RoutineDayAdmin(admin.ModelAdmin):
    list_display = ['routine', 'label', 'user', 'order']
    search_fields = ['label', 'routine__name']


@admin.register(RoutineExerciseTarget)
class RoutineExerciseTargetAdmin(admin.ModelAdmin):
    list_display = ['routine_day', 'exercise', 'target_sets', 'target_reps']


class SessionEntryInline(admin.TabularInline):
    model = SessionEntry
    extra = 0


@admin.register(WorkoutSession)
class WorkoutSessionAdmin(admin.ModelAdmin):
    list_display = ['date', 'user', 'routine_day', 'duration_minutes']
    list_filter = ['date']
    search_fields = ['user__email']
    inlines = [SessionEntryInline]


@admin.register(SessionEntry)
class SessionEntryAdmin(admin.ModelAdmin):
    list_display = ['session', 'exercise', 'user']


@admin.register(SetLog)
class SetLogAdmin(admin.ModelAdmin):
    list_display = ['entry', 'set_number', 'reps', 'weight']
