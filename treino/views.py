"""
Training views.

Every CRUD view is owner scoped through the bases in ``core.views``. The nested resources
(``RoutineDay``, ``RoutineExerciseTarget``, ``SessionEntry``, ``SetLog``) use
``ChildCreateView`` so the parent id from the URL is re-checked against the logged in user on
every request, never trusted from the form.
"""

from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Count, Max
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from core.views import (
    ChildCreateView,
    OwnerCreateView,
    OwnerDeleteView,
    OwnerDetailView,
    OwnerListView,
    OwnerUpdateView,
)

from . import progression, protocol
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
        # A ficha ativa vai inteira para a tela, e nao so contada: o hub existe para levar a
        # pessoa ao treino da semana, e um contador '1' nao diz qual ficha nem leva a lugar
        # nenhum util.
        active_routines = list(
            WorkoutRoutine.objects.filter(user=user, is_active=True)
            .prefetch_related('days__exercise_targets')
        )
        context['active_routines'] = active_routines
        context['routine_count'] = len(active_routines)
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
        return super().get_queryset().prefetch_related(
            'days__muscle_groups', 'days__exercise_targets__exercise',
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # The description is prose the person wrote by hand, with headings in it. Reading it
        # back as sections is what lets the template typeset it instead of dumping one wall
        # of text — see ``treino/protocol.py``.
        context['sections'] = protocol.parse_sections(self.object.description)
        return context


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


# ── Registrar treino: a tela única ───────────────────────────────────────────
#
# O CRUD acima resolve cadastro, não execução: registrar um treino por ele custa uma
# página por série. Estas views resolvem o caso real — de pé na academia, no intervalo de
# noventa segundos — numa tela só, com as séries prescritas já montadas, o que foi
# levantado da última vez ao lado, e a sugestão de carga quando a dupla progressão fecha.


MAX_REPS = 500
MAX_WEIGHT = Decimal('1000')


class SessionRunPickView(LoginRequiredMixin, TemplateView):
    """Escolha da divisão do dia, com a alternância sugerida a partir do último treino."""

    template_name = 'treino/session_run_pick.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        today = timezone.localdate()

        days = list(
            RoutineDay.objects.filter(user=user, routine__is_active=True)
            .select_related('routine')
            .annotate(target_count=Count('exercise_targets'))
            .order_by('routine__name', 'order')
        )
        context['days'] = days
        context['suggested'] = progression.next_day_after(user, days, today)
        context['today'] = today
        context['today_session'] = (
            WorkoutSession.objects.filter(user=user, date=today)
            .select_related('routine_day')
            .first()
        )
        context['pending_morning'] = progression.pending_morning_session(user, today)
        context['streak_weeks'] = progression.morning_streak(user, today)
        context['reintroduction_weeks'] = progression.REINTRODUCTION_WEEKS
        return context


class SessionRunView(LoginRequiredMixin, View):
    """
    Registro de uma sessão inteira numa tela.

    GET monta (ou recupera) a sessão de hoje para a divisão pedida e devolve uma linha por
    série prescrita. POST grava tudo de uma vez: campo de repetições em branco apaga a série
    correspondente, então corrigir um erro é apagar o número, não caçar um botão de excluir.

    A divisão vem da URL e é sempre refetchada com ``user=request.user`` — mesma garantia do
    ``ChildCreateView``: pk de outra pessoa dá 404 antes de qualquer escrita.
    """

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            self.day = get_object_or_404(
                RoutineDay.objects.select_related('routine'), pk=kwargs['pk'], user=request.user,
            )
        return super().dispatch(request, *args, **kwargs)

    def get_targets(self):
        return list(
            self.day.exercise_targets.select_related('exercise', 'exercise__muscle_group')
            .order_by('order', 'pk')
        )

    def today_session(self):
        """A sessão de hoje para esta divisão, se já existir. O GET nunca cria."""
        return WorkoutSession.objects.filter(
            user=self.request.user, routine_day=self.day, date=timezone.localdate(),
        ).first()

    def entry_for(self, session, target, position):
        """A entrada do alvo dentro da sessão, criada na primeira série que chega."""
        entry, created = SessionEntry.objects.get_or_create(
            session=session, exercise=target.exercise,
            defaults={
                'user': self.request.user,
                'order': position,
                'rest_seconds': target.rest_seconds,
            },
        )
        if not created and entry.rest_seconds is None and target.rest_seconds:
            entry.rest_seconds = target.rest_seconds
            entry.save(update_fields=['rest_seconds'])
        return entry

    def build_rows(self, targets, session, today):
        """
        Uma linha por alvo: séries prescritas, o que já foi gravado hoje e a sugestão.

        As linhas são indexadas pelo alvo, não pela entrada, justamente para que a tela
        exista antes da sessão.
        """
        logged = {}
        if session is not None:
            for set_log in SetLog.objects.filter(
                user=self.request.user, entry__session=session,
            ).select_related('entry'):
                logged.setdefault(set_log.entry.exercise_id, {})[set_log.set_number] = set_log

        rows = []
        for target in targets:
            hint = progression.suggestion_for(self.request.user, target, today)
            done = logged.get(target.exercise_id, {})
            previous_sets = hint['last_sets']
            sets = []
            for number in range(1, target.target_sets + 1):
                current = done.get(number)
                sets.append({
                    'number': number,
                    'reps': current.reps if current else None,
                    'weight': current.weight if current else None,
                    'previous': previous_sets[number - 1] if number <= len(previous_sets) else None,
                })
            rows.append({
                'target': target,
                'sets': sets,
                'hint': hint,
                'is_timed': progression.top_of_range(target.target_reps) is None,
                'done_count': len(done),
                'complete': len(done) >= target.target_sets,
            })
        return rows

    def get(self, request, pk):
        today = timezone.localdate()
        targets = self.get_targets()
        session = self.today_session()
        rows = self.build_rows(targets, session, today)
        return TemplateResponse(request, 'treino/session_run.html', {
            'day': self.day,
            'session': session,
            'today': today,
            'rows': rows,
            'total_sets': sum(len(row['sets']) for row in rows),
            'done_sets': sum(row['done_count'] for row in rows),
            'streak_weeks': progression.morning_streak(request.user, today),
            'reintroduction_weeks': progression.REINTRODUCTION_WEEKS,
            'pending_morning': progression.pending_morning_session(request.user, today),
        })

    @transaction.atomic
    def post(self, request, pk):
        targets = self.get_targets()
        session = self.today_session()
        submitted = self.read_submission(request, targets)

        if session is None:
            if not submitted:
                messages.info(request, 'Nenhuma série preenchida.')
                return redirect('treino:session_run', pk=self.day.pk)
            session = WorkoutSession.objects.create(
                user=request.user, routine_day=self.day, date=timezone.localdate(),
            )

        saved = 0
        for position, target in enumerate(targets, start=1):
            values = submitted.get(target.pk, {})
            existing = SessionEntry.objects.filter(session=session, exercise=target.exercise).first()
            if not values and existing is None:
                continue
            entry = existing or self.entry_for(session, target, position)
            for number in range(1, target.target_sets + 1):
                pair = values.get(number)
                if pair is None:
                    SetLog.objects.filter(user=request.user, entry=entry, set_number=number).delete()
                    continue
                SetLog.objects.update_or_create(
                    entry=entry, set_number=number,
                    defaults={
                        'user': request.user,
                        'reps': pair['reps'],
                        'weight': pair['weight'] or Decimal('0'),
                    },
                )
                saved += 1

        session.duration_minutes = self.clean_int(request.POST.get('duration_minutes'), 600)
        session.notes = (request.POST.get('notes') or '').strip()[:2000]
        session.save(update_fields=['duration_minutes', 'notes', 'updated_at'])

        # Entrada que ficou sem série nenhuma não é histórico, é rascunho: sai.
        SessionEntry.objects.filter(session=session, sets__isnull=True).delete()

        # E sessão sem entrada nenhuma também não: some, em vez de poluir a frequência
        # da semana com um treino que não aconteceu.
        if not session.entries.exists():
            session.delete()
            messages.info(request, 'Nenhuma série registrada — a sessão foi descartada.')
            if request.POST.get('finish'):
                return redirect('treino:session_run_pick')
            return redirect('treino:session_run', pk=self.day.pk)

        if request.POST.get('finish'):
            messages.success(request, 'Treino registrado: {0} séries.'.format(saved))
            return redirect(session.get_absolute_url())

        messages.success(request, 'Séries salvas.')
        return redirect('treino:session_run', pk=self.day.pk)

    def read_submission(self, request, targets):
        """
        Lê o formulário inteiro antes de tocar no banco.

        Devolve ``{target_pk: {n: {'reps': int, 'weight': Decimal|None}}}``, só com séries
        que trouxeram repetição válida. Ler primeiro é o que permite decidir se vale a pena
        criar a sessão.
        """
        submitted = {}
        for target in targets:
            for number in range(1, target.target_sets + 1):
                prefix = 't{0}s{1}'.format(target.pk, number)
                reps = self.clean_int(request.POST.get(prefix + 'reps'), MAX_REPS)
                if reps is None:
                    continue
                submitted.setdefault(target.pk, {})[number] = {
                    'reps': reps,
                    'weight': self.clean_decimal(request.POST.get(prefix + 'kg')),
                }
        return submitted

    @staticmethod
    def clean_int(raw, ceiling):
        """Inteiro dentro do limite, ou ``None``. Lixo digitado vira campo vazio, não erro 500."""
        if raw is None or not str(raw).strip():
            return None
        try:
            value = int(str(raw).strip())
        except (TypeError, ValueError):
            return None
        if value < 1 or value > ceiling:
            return None
        return value

    @staticmethod
    def clean_decimal(raw):
        """Carga aceitando vírgula decimal: quem digita no celular escreve 62,5."""
        if raw is None or not str(raw).strip():
            return None
        try:
            value = Decimal(str(raw).strip().replace(',', '.'))
        except (InvalidOperation, TypeError, ValueError):
            return None
        if value < 0 or value > MAX_WEIGHT:
            return None
        return value.quantize(Decimal('0.01'))


class SessionMorningAfterView(LoginRequiredMixin, View):
    """
    Resposta da regra das 24h.

    POST só: é escrita e não tem tela própria. ``next`` volta para a página de onde veio,
    validado contra uma lista fixa de nomes de rota — nunca redireciona para URL arbitrária
    vinda do formulário.
    """

    ALLOWED_NEXT = {'treino:session_run_pick', 'treino:index', 'treino:session_list'}

    def post(self, request, pk):
        session = get_object_or_404(WorkoutSession, pk=pk, user=request.user)
        answer = request.POST.get('morning_after')
        if answer not in dict(WorkoutSession.MorningAfter.choices):
            messages.error(request, 'Escolha uma das duas respostas.')
            return redirect('treino:session_run_pick')

        session.morning_after = answer
        session.save(update_fields=['morning_after', 'updated_at'])
        if answer == WorkoutSession.MorningAfter.WORSE:
            messages.info(request, 'Anotado. Recue carga e volume no próximo treino.')
        else:
            messages.success(request, 'Anotado. Pode manter a carga.')

        target = request.POST.get('next')
        return redirect(target if target in self.ALLOWED_NEXT else 'treino:session_run_pick')
