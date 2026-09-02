"""
Nutrition views. Owner scoped through the same bases used by ``saude`` and ``treino``.

``Meal`` and ``MealItem`` follow the nested-resource pattern from ``treino``
(``ChildCreateView``); ``DailyLog`` is the one list that takes a ``?data=`` query param
instead of pagination, because a day's log is naturally read as a whole, not paged.
"""

from datetime import date as date_cls

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import TemplateView

from billing.gating import diet_limit_exceeded
from core.views import (
    ChildCreateView,
    OwnerCreateView,
    OwnerDeleteView,
    OwnerDetailView,
    OwnerListView,
    OwnerUpdateView,
)

from .forms import DailyLogForm, DietForm, FoodForm, MealForm, MealItemForm, WeightLogForm
from .models import DailyLog, Diet, Food, Meal, MealItem, WeightLog, daily_totals, estimate_daily_calories
from .plans import plan_comparison


class NutritionIndexView(LoginRequiredMixin, TemplateView):
    """Hub of the nutrition area: today's adherence against the active plan, weight trend."""

    template_name = 'nutricao/index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        today = timezone.localdate()

        context['food_count'] = Food.objects.filter(user=user).count()
        context['diet_count'] = Diet.objects.filter(user=user, is_active=True).count()
        context['active_diet'] = Diet.objects.filter(user=user, is_active=True).first()
        context['today'] = today
        context['today_totals'] = daily_totals(user, today)
        context['today_logs'] = DailyLog.objects.filter(user=user, date=today).select_related('food')
        context['latest_weight'] = WeightLog.objects.filter(user=user).order_by('-date').first()

        # Comparador de cardápios: a dieta ativa contra a anterior, ambas do próprio dono.
        # Sem duas dietas cadastradas o bloco simplesmente não aparece (``plans``).
        context['plan_comparison'] = plan_comparison(
            user,
            profile=getattr(user, 'profile', None),
            weight_kg=context['latest_weight'].weight_kg if context['latest_weight'] else None,
        )
        return context


# ── Alimentos ────────────────────────────────────────────────────────────────


class FoodListView(OwnerListView):
    model = Food
    template_name = 'nutricao/food_list.html'


class FoodDetailView(OwnerDetailView):
    model = Food
    template_name = 'nutricao/food_detail.html'


class FoodCreateView(OwnerCreateView):
    model = Food
    form_class = FoodForm
    template_name = 'nutricao/object_form.html'
    success_message = 'Alimento cadastrado.'
    extra_context = {'page_kicker': 'Alimentos', 'page_title': 'Novo alimento'}


class FoodUpdateView(OwnerUpdateView):
    model = Food
    form_class = FoodForm
    template_name = 'nutricao/object_form.html'
    extra_context = {'page_kicker': 'Alimentos', 'page_title': 'Editar alimento'}


class FoodDeleteView(OwnerDeleteView):
    model = Food
    success_url = reverse_lazy('nutricao:food_list')
    success_message = 'Alimento excluído.'
    delete_warning = 'Isso também remove este alimento de refeições de dietas e do registro diário.'


# ── Dietas ───────────────────────────────────────────────────────────────────


class DietListView(OwnerListView):
    model = Diet
    template_name = 'nutricao/diet_list.html'


class DietDetailView(OwnerDetailView):
    model = Diet
    template_name = 'nutricao/diet_detail.html'

    def get_queryset(self):
        return super().get_queryset().prefetch_related('meals__items__food')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        latest_weight = WeightLog.objects.filter(user=self.request.user).order_by('-date').first()
        context['suggested_calories'] = estimate_daily_calories(
            self.request.user.profile,
            latest_weight.weight_kg if latest_weight else None,
            self.object.goal,
        )
        return context


class DietPlanLimitMixin:
    """
    Blocks activating a diet past the plan's ``active_diets`` limit (Free = 1, PRD 10.2).

    Checked on the view, not the form: the limit depends on who is asking, which a plain
    ``ModelForm`` has no way to know without the request being threaded through it.
    """

    limit_excluding_self = False

    def form_valid(self, form):
        if form.cleaned_data.get('is_active'):
            excluding_pk = self.object.pk if self.limit_excluding_self and self.object else None
            if diet_limit_exceeded(self.request.user, excluding_pk=excluding_pk):
                form.add_error(
                    'is_active',
                    'Seu plano permite só uma dieta ativa por vez. Desative outra ou '
                    'assine o Premium para ter dietas ilimitadas.',
                )
                return self.form_invalid(form)
        return super().form_valid(form)


class DietCreateView(DietPlanLimitMixin, OwnerCreateView):
    model = Diet
    form_class = DietForm
    template_name = 'nutricao/object_form.html'
    success_message = 'Dieta criada.'
    extra_context = {'page_kicker': 'Dietas', 'page_title': 'Nova dieta'}


class DietUpdateView(DietPlanLimitMixin, OwnerUpdateView):
    model = Diet
    form_class = DietForm
    template_name = 'nutricao/object_form.html'
    extra_context = {'page_kicker': 'Dietas', 'page_title': 'Editar dieta'}
    limit_excluding_self = True


class DietDeleteView(OwnerDeleteView):
    model = Diet
    success_url = reverse_lazy('nutricao:diet_list')
    success_message = 'Dieta excluída.'
    delete_warning = 'Isso também apaga as refeições e itens cadastrados nesta dieta.'


class MealCreateView(ChildCreateView):
    model = Meal
    form_class = MealForm
    template_name = 'nutricao/object_form.html'
    parent_model = Diet
    parent_field = 'diet'
    parent_context_name = 'diet'
    success_message = 'Refeição adicionada.'
    extra_context = {'page_kicker': 'Dietas', 'page_title': 'Nova refeição'}


class MealDetailView(OwnerDetailView):
    model = Meal
    template_name = 'nutricao/meal_detail.html'

    def get_queryset(self):
        return super().get_queryset().select_related('diet').prefetch_related('items__food')


class MealUpdateView(OwnerUpdateView):
    model = Meal
    form_class = MealForm
    template_name = 'nutricao/object_form.html'
    extra_context = {'page_kicker': 'Dietas', 'page_title': 'Editar refeição'}


class MealDeleteView(OwnerDeleteView):
    model = Meal
    success_message = 'Refeição excluída.'

    def get_success_url(self):
        return self.object.diet.get_absolute_url()


class MealItemCreateView(ChildCreateView):
    model = MealItem
    form_class = MealItemForm
    template_name = 'nutricao/object_form.html'
    parent_model = Meal
    parent_field = 'meal'
    parent_context_name = 'meal'
    success_message = 'Item adicionado.'
    extra_context = {'page_kicker': 'Dietas', 'page_title': 'Adicionar item'}

    def get_success_url(self):
        return self.parent.get_absolute_url()


class MealItemDeleteView(OwnerDeleteView):
    model = MealItem
    success_message = 'Item removido.'

    def get_success_url(self):
        return self.object.meal.get_absolute_url()


# ── Registro diário ──────────────────────────────────────────────────────────


class DailyLogListView(LoginRequiredMixin, TemplateView):
    """One day at a time, chosen via ``?data=YYYY-MM-DD`` — defaults to today."""

    template_name = 'nutricao/dailylog_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        raw_date = self.request.GET.get('data')
        try:
            selected_date = date_cls.fromisoformat(raw_date) if raw_date else timezone.localdate()
        except ValueError:
            selected_date = timezone.localdate()

        context['selected_date'] = selected_date
        context['today'] = timezone.localdate()
        context['logs'] = DailyLog.objects.filter(user=user, date=selected_date).select_related('food')
        context['totals'] = daily_totals(user, selected_date)
        context['active_diet'] = Diet.objects.filter(user=user, is_active=True).first()
        return context


class DailyLogCreateView(OwnerCreateView):
    model = DailyLog
    form_class = DailyLogForm
    template_name = 'nutricao/object_form.html'
    success_message = 'Registrado.'
    extra_context = {'page_kicker': 'Registro diário', 'page_title': 'Registrar consumo'}

    def get_initial(self):
        initial = super().get_initial()
        raw_date = self.request.GET.get('data')
        if raw_date:
            initial['date'] = raw_date
        return initial

    def get_success_url(self):
        return f"{reverse('nutricao:dailylog_list')}?data={self.object.date.isoformat()}"


class DailyLogDeleteView(OwnerDeleteView):
    model = DailyLog
    success_message = 'Registro excluído.'

    def get_success_url(self):
        return f"{reverse('nutricao:dailylog_list')}?data={self.object.date.isoformat()}"


# ── Peso corporal ────────────────────────────────────────────────────────────


class WeightLogListView(OwnerListView):
    model = WeightLog
    template_name = 'nutricao/weightlog_list.html'
    paginate_by = 60  # a lista alimenta o gráfico também; não vale a pena paginar cedo

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        entries = list(WeightLog.objects.filter(user=self.request.user).order_by('date'))
        context['chart_points'] = [
            {'date': entry.date.isoformat(), 'weight': float(entry.weight_kg)} for entry in entries
        ]
        context['target_weight'] = self.request.user.profile.target_weight_kg
        return context


class WeightLogCreateView(OwnerCreateView):
    model = WeightLog
    form_class = WeightLogForm
    template_name = 'nutricao/object_form.html'
    success_url = reverse_lazy('nutricao:weightlog_list')
    success_message = 'Peso registrado.'
    extra_context = {'page_kicker': 'Peso', 'page_title': 'Registrar peso'}


class WeightLogUpdateView(OwnerUpdateView):
    model = WeightLog
    form_class = WeightLogForm
    template_name = 'nutricao/object_form.html'
    success_url = reverse_lazy('nutricao:weightlog_list')
    extra_context = {'page_kicker': 'Peso', 'page_title': 'Editar peso'}


class WeightLogDeleteView(OwnerDeleteView):
    model = WeightLog
    success_url = reverse_lazy('nutricao:weightlog_list')
    success_message = 'Registro de peso excluído.'


class WeightProgressDataView(LoginRequiredMixin, TemplateView):
    """JSON feed for the weight chart, mirroring ``treino``'s exercise-progress endpoint."""

    def get(self, request):
        entries = WeightLog.objects.filter(user=request.user).order_by('date')
        points = [{'date': e.date.isoformat(), 'weight': float(e.weight_kg)} for e in entries]
        return JsonResponse({'points': points, 'target': float(request.user.profile.target_weight_kg or 0) or None})
