"""
Training views.

Every CRUD view is owner scoped through the bases in ``core.views``. The nested resources
(``RoutineDay``, ``RoutineExerciseTarget``, ``SessionEntry``, ``SetLog``) use
``ChildCreateView`` so the parent id from the URL is re-checked against the logged in user on
every request, never trusted from the form.
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Max
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.views.generic import TemplateView

from core.views import (
    ChildCreateView,
    OwnerCreateView,
    OwnerDeleteView,
    OwnerDetailView,
    OwnerListView,
    OwnerUpdateView,
)

from .forms import (
    ExerciseForm,
    MuscleGroupForm,
    RoutineDayForm,
    RoutineExerciseTargetForm,
    SessionEntryForm,
    SetLogForm,
    WorkoutRoutineForm,
    WorkoutSessionForm,
)
from .models import (
    Exercise,
    MuscleGroup,
    RoutineDay,
    RoutineExerciseTarget,
    SessionEntry,
    SetLog,
    WorkoutRoutine,
    WorkoutSession,
    week_bounds,
)


class TrainingIndexView(LoginRequiredMixin, TemplateView):
    """Hub of the training area: counters, the week's volume and frequency."""

    template_name = 'treino/index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        monday, sunday = week_bounds()

        context['muscle_group_count'] = MuscleGroup.objects.filter(user=user).count()
        context['exercise_count'] = Exercise.objects.filter(user=user).count()
        context['routine_count'] = WorkoutRoutine.objects.filter(user=user, is_active=True).count()
        context['week_start'] = monday
        context['week_end'] = sunday
        context['sessions_this_week'] = WorkoutSession.objects.filter(
            user=user, date__gte=monday, date__lte=sunday
        ).count()
        context['recent_sessions'] = WorkoutSession.objects.filter(user=user).select_related(
            'routine_day', 'routine_day__routine'
        )[:5]
        context['volume_by_group'] = _volume_by_muscle_group(user, monday, sunday)
        return context


def _volume_by_muscle_group(user, start, end):
    """
    Sets logged per muscle group within [start, end].

    A set can train more than one group at once (compound lifts): each ``SetLog`` counts
    toward every muscle group its exercise is tagged with, which today is a single FK — so
    each set counts once, toward its exercise's group.
    """
    return (
        SetLog.objects.filter(
            user=user, entry__session__date__gte=start, entry__session__date__lte=end,
        )
        .values('entry__exercise__muscle_group__name')
        .annotate(sets=Count('id'))
        .order_by('-sets')
    )


# ── Grupos musculares ────────────────────────────────────────────────────────


class MuscleGroupListView(OwnerListView):
    model = MuscleGroup
    template_name = 'treino/muscle_group_list.html'


class MuscleGroupDetailView(OwnerDetailView):
    model = MuscleGroup
    template_name = 'treino/muscle_group_detail.html'

    def get_queryset(self):
        return super().get_queryset().prefetch_related('exercises')


class MuscleGroupCreateView(OwnerCreateView):
    model = MuscleGroup
    form_class = MuscleGroupForm
    template_name = 'treino/object_form.html'
    success_message = 'Grupo muscular criado.'
    extra_context = {'page_kicker': 'Grupos musculares', 'page_title': 'Novo grupo muscular'}


class MuscleGroupUpdateView(OwnerUpdateView):
    model = MuscleGroup
    form_class = MuscleGroupForm
    template_name = 'treino/object_form.html'
    extra_context = {'page_kicker': 'Grupos musculares', 'page_title': 'Editar grupo muscular'}


class MuscleGroupDeleteView(OwnerDeleteView):
    model = MuscleGroup
    success_url = reverse_lazy('treino:muscle_group_list')
    success_message = 'Grupo muscular excluído.'
    delete_warning = 'Isso também apaga os exercícios deste grupo e todo o histórico de séries ligado a eles.'


# ── Exercícios ───────────────────────────────────────────────────────────────


class ExerciseListView(OwnerListView):
    model = Exercise
    template_name = 'treino/exercise_list.html'

    def get_queryset(self):
        return super().get_queryset().select_related('muscle_group')


class ExerciseDetailView(OwnerDetailView):
    model = Exercise
    template_name = 'treino/exercise_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['progress'] = list(_load_progress(self.object))
        return context


def _load_progress(exercise):
    """Heaviest set per session, oldest first — the series the load-evolution chart plots."""
    entries = (
        SessionEntry.objects.filter(exercise=exercise, user_id=exercise.user_id)
        # `heaviest_set` (not `top_weight`): the annotation alias must not collide with the
        # `SessionEntry.top_weight` property, or Django's ORM tries to overwrite it and
        # raises AttributeError — a read-only property has no setter.
        .annotate(heaviest_set=Max('sets__weight'))
        .exclude(heaviest_set__isnull=True)
        .select_related('session')
        .order_by('session__date')
    )
    return [{'date': entry.session.date.isoformat(), 'weight': float(entry.heaviest_set)} for entry in entries]


class ExerciseCreateView(OwnerCreateView):
    model = Exercise
    form_class = ExerciseForm
    template_name = 'treino/object_form.html'
    success_message = 'Exercício cadastrado.'
    extra_context = {'page_kicker': 'Exercícios', 'page_title': 'Novo exercício'}


class ExerciseUpdateView(OwnerUpdateView):
    model = Exercise
    form_class = ExerciseForm
    template_name = 'treino/object_form.html'
    extra_context = {'page_kicker': 'Exercícios', 'page_title': 'Editar exercício'}


class ExerciseDeleteView(OwnerDeleteView):
    model = Exercise
    success_url = reverse_lazy('treino:exercise_list')
    success_message = 'Exercício excluído.'
    delete_warning = 'Isso também apaga o histórico de séries deste exercício em todas as sessões e o remove de qualquer ficha.'


# ── Fichas ───────────────────────────────────────────────────────────────────


class WorkoutRoutineListView(OwnerListView):
    model = WorkoutRoutine
    template_name = 'treino/routine_list.html'


class WorkoutRoutineDetailView(OwnerDetailView):
    model = WorkoutRoutine
    template_name = 'treino/routine_detail.html'

    def get_queryset(self):
        return super().get_queryset().prefetch_related('days__exercise_targets__exercise')


class WorkoutRoutineCreateView(OwnerCreateView):
    model = WorkoutRoutine
    form_class = WorkoutRoutineForm
    template_name = 'treino/object_form.html'
    success_message = 'Ficha criada.'
    extra_context = {'page_kicker': 'Fichas', 'page_title': 'Nova ficha'}


class WorkoutRoutineUpdateView(OwnerUpdateView):
    model = WorkoutRoutine
    form_class = WorkoutRoutineForm
    template_name = 'treino/object_form.html'
    extra_context = {'page_kicker': 'Fichas', 'page_title': 'Editar ficha'}


class WorkoutRoutineDeleteView(OwnerDeleteView):
    model = WorkoutRoutine
    success_url = reverse_lazy('treino:routine_list')
    success_message = 'Ficha excluída.'


class RoutineDayCreateView(ChildCreateView):
    model = RoutineDay
    form_class = RoutineDayForm
    template_name = 'treino/object_form.html'
    parent_model = WorkoutRoutine
    parent_field = 'routine'
    parent_context_name = 'routine'
    success_message = 'Divisão adicionada.'
    extra_context = {'page_kicker': 'Fichas', 'page_title': 'Nova divisão'}


class RoutineDayDetailView(OwnerDetailView):
    model = RoutineDay
    template_name = 'treino/routine_day_detail.html'

    def get_queryset(self):
        return super().get_queryset().select_related('routine').prefetch_related(
            'muscle_groups', 'exercise_targets__exercise'
        )


class RoutineDayUpdateView(OwnerUpdateView):
    model = RoutineDay
    form_class = RoutineDayForm
    template_name = 'treino/object_form.html'
    extra_context = {'page_kicker': 'Fichas', 'page_title': 'Editar divisão'}


class RoutineDayDeleteView(OwnerDeleteView):
    model = RoutineDay
    success_message = 'Divisão excluída.'

    def get_success_url(self):
        return self.object.routine.get_absolute_url()


class RoutineExerciseTargetCreateView(ChildCreateView):
    model = RoutineExerciseTarget
    form_class = RoutineExerciseTargetForm
    template_name = 'treino/object_form.html'
    parent_model = RoutineDay
    parent_field = 'routine_day'
    parent_context_name = 'routine_day'
    success_message = 'Exercício adicionado à divisão.'
    extra_context = {'page_kicker': 'Fichas', 'page_title': 'Adicionar exercício'}

    def get_success_url(self):
        return self.parent.get_absolute_url()


class RoutineExerciseTargetDeleteView(OwnerDeleteView):
    model = RoutineExerciseTarget
    success_message = 'Exercício removido da divisão.'

    def get_success_url(self):
        return self.object.routine_day.get_absolute_url()


# ── Sessões de treino ────────────────────────────────────────────────────────


class WorkoutSessionListView(OwnerListView):
    model = WorkoutSession
    template_name = 'treino/session_list.html'

    def get_queryset(self):
        return super().get_queryset().select_related('routine_day', 'routine_day__routine')


class WorkoutSessionDetailView(OwnerDetailView):
    model = WorkoutSession
    template_name = 'treino/session_detail.html'

    def get_queryset(self):
        return super().get_queryset().select_related('routine_day').prefetch_related(
            'entries__exercise', 'entries__sets'
        )


class WorkoutSessionCreateView(OwnerCreateView):
    model = WorkoutSession
    form_class = WorkoutSessionForm
    template_name = 'treino/object_form.html'
    success_message = 'Sessão registrada.'
    extra_context = {'page_kicker': 'Sessões', 'page_title': 'Nova sessão'}


class WorkoutSessionUpdateView(OwnerUpdateView):
    model = WorkoutSession
    form_class = WorkoutSessionForm
    template_name = 'treino/object_form.html'
    extra_context = {'page_kicker': 'Sessões', 'page_title': 'Editar sessão'}


class WorkoutSessionDeleteView(OwnerDeleteView):
    model = WorkoutSession
    success_url = reverse_lazy('treino:session_list')
    success_message = 'Sessão excluída.'


class SessionEntryCreateView(ChildCreateView):
    model = SessionEntry
    form_class = SessionEntryForm
    template_name = 'treino/object_form.html'
    parent_model = WorkoutSession
    parent_field = 'session'
    parent_context_name = 'session'
    success_message = 'Exercício adicionado à sessão.'
    extra_context = {'page_kicker': 'Sessões', 'page_title': 'Adicionar exercício'}

    def get_success_url(self):
        return self.parent.get_absolute_url()


class SessionEntryDeleteView(OwnerDeleteView):
    model = SessionEntry
    success_message = 'Exercício removido da sessão.'

    def get_success_url(self):
        return self.object.session.get_absolute_url()


class SetLogCreateView(ChildCreateView):
    model = SetLog
    form_class = SetLogForm
    template_name = 'treino/object_form.html'
    parent_model = SessionEntry
    parent_field = 'entry'
    parent_context_name = 'entry'
    success_message = 'Série registrada.'
    extra_context = {'page_kicker': 'Sessões', 'page_title': 'Registrar série'}

    def get_initial(self):
        initial = super().get_initial()
        next_number = self.parent.sets.count() + 1
        initial['set_number'] = next_number
        return initial

    def get_success_url(self):
        return self.parent.get_absolute_url()


class SetLogDeleteView(OwnerDeleteView):
    model = SetLog
    success_message = 'Série excluída.'

    def get_success_url(self):
        return self.object.entry.get_absolute_url()


# ── Evolução de carga ────────────────────────────────────────────────────────


class ExerciseProgressDataView(LoginRequiredMixin, TemplateView):
    """JSON feed for the load-evolution chart on the exercise detail page."""

    def get(self, request, pk):
        exercise = Exercise.objects.filter(pk=pk, user=request.user).first()
        if exercise is None:
            return JsonResponse({'points': []}, status=404)
        return JsonResponse({'points': _load_progress(exercise)})
