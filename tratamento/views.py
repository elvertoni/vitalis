"""
Treatment screens: the shot log, side effects and the "next shot" card.

Every view inherits from the owner-scoped bases in ``core.views``; none of them filters
by user on its own.
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import FormView
from django.utils import timezone

from core.views import (
    OwnerCreateView,
    OwnerDeleteView,
    OwnerListView,
    OwnerUpdateView,
)
from saude.models import Medication

from .forms import InjectionForm, OnboardingForm, SideEffectForm
from .models import Injection, SideEffect, missed_due_date, next_due_date, suggested_site


def schedule_cards(user, today=None):
    """
    One card per medication that already has a shot on record: next dose day, the dose
    and site to suggest, and a late flag. Read by the treatment index and, later, the Home.

    A medication enters only after its first shot is logged. Until then nothing says it
    is an injectable, and a card for every pill in the cabinet would bury the one that
    matters.
    """
    today = today or timezone.localdate()
    medications = (
        Medication.objects.filter(user=user, is_active=True, injections__isnull=False)
        .distinct()
        .order_by('name')
    )
    cards = []
    for medication in medications:
        last = medication.injections.order_by('-applied_at').first()
        due = next_due_date(medication, today)
        cards.append({
            'medication': medication,
            'last': last,
            'next_due': due,
            'days_until': (due - today).days if due else None,
            'applied_today': timezone.localtime(last.applied_at).date() == today,
            'missed': missed_due_date(medication, today),
            'suggested_site': Injection.Site(suggested_site(user, medication)).label,
        })
    return cards


class TreatmentIndexView(OwnerListView):
    model = Injection
    template_name = 'tratamento/index.html'

    def get_queryset(self):
        return super().get_queryset().select_related('medication')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['cards'] = schedule_cards(user)
        context['recent_side_effects'] = (
            SideEffect.objects.filter(user=user).select_related('injection__medication')[:5]
        )
        return context


class InjectionCreateView(OwnerCreateView):
    model = Injection
    form_class = InjectionForm
    template_name = 'tratamento/object_form.html'
    success_url = reverse_lazy('tratamento:index')
    success_message = 'Aplicação registrada.'
    extra_context = {'page_kicker': 'Tratamento', 'page_title': 'Registrar aplicação'}

    def get_initial(self):
        """
        Pre-fills from the last shot: same medication, same dose, next site in rotation.
        Titration changes the dose now and then, so it stays editable, never locked.
        """
        initial = super().get_initial()
        initial['applied_at'] = timezone.localtime().replace(second=0, microsecond=0)
        last = (
            Injection.objects.filter(user=self.request.user, medication__is_active=True)
            .select_related('medication')
            .order_by('-applied_at')
            .first()
        )
        if last:
            initial['medication'] = last.medication
            initial['dose_mg'] = last.dose_mg
            initial['site'] = suggested_site(self.request.user, last.medication)
        return initial


class InjectionUpdateView(OwnerUpdateView):
    model = Injection
    form_class = InjectionForm
    template_name = 'tratamento/object_form.html'
    success_url = reverse_lazy('tratamento:index')
    extra_context = {
        'page_kicker': 'Tratamento',
        'page_title': 'Editar aplicação',
        'delete_url_name': 'tratamento:injection_delete',
    }


class InjectionDeleteView(OwnerDeleteView):
    model = Injection
    success_url = reverse_lazy('tratamento:index')
    success_message = 'Aplicação excluída.'
    delete_warning = 'Os efeitos colaterais ligados a esta aplicação continuam registrados, só sem o vínculo.'


class SideEffectListView(OwnerListView):
    model = SideEffect
    template_name = 'tratamento/sideeffect_list.html'

    def get_queryset(self):
        return super().get_queryset().select_related('injection__medication')


class SideEffectCreateView(OwnerCreateView):
    model = SideEffect
    form_class = SideEffectForm
    template_name = 'tratamento/object_form.html'
    success_url = reverse_lazy('tratamento:sideeffect_list')
    success_message = 'Efeito registrado.'
    extra_context = {'page_kicker': 'Tratamento', 'page_title': 'Registrar efeito colateral'}

    def get_initial(self):
        """Links to the latest shot by default: nausea usually follows the week's dose."""
        initial = super().get_initial()
        last = Injection.objects.filter(user=self.request.user).order_by('-applied_at').first()
        if last:
            initial['injection'] = last
        return initial


class SideEffectUpdateView(OwnerUpdateView):
    model = SideEffect
    form_class = SideEffectForm
    template_name = 'tratamento/object_form.html'
    success_url = reverse_lazy('tratamento:sideeffect_list')
    extra_context = {
        'page_kicker': 'Tratamento',
        'page_title': 'Editar efeito colateral',
        'delete_url_name': 'tratamento:sideeffect_delete',
    }


class SideEffectDeleteView(OwnerDeleteView):
    model = SideEffect
    success_url = reverse_lazy('tratamento:sideeffect_list')
    success_message = 'Efeito excluído.'


class OnboardingView(LoginRequiredMixin, FormView):
    """
    First access: profile, first weighing and, optionally, the injectable, in one POST.

    It writes rows owned by ``request.user`` only and never reads a primary key from the
    form, so there is no related field to narrow — that is why it does not need the
    ``OwnerFormMixin``. Can be revisited later: it pre-fills from what is on file.
    """

    form_class = OnboardingForm
    template_name = 'tratamento/onboarding.html'

    def get_initial(self):
        from nutricao.plans import latest_weight

        profile = self.request.user.profile
        return {
            'height_cm': profile.height_cm,
            'target_weight_kg': profile.target_weight_kg,
            'birth_date': profile.birth_date,
            'sex': profile.sex,
            'current_weight_kg': latest_weight(self.request.user),
            'reminder_time': '08:00',
        }

    def form_valid(self, form):
        medication = form.save(self.request.user)
        if medication:
            messages.success(self.request, f'Tudo pronto. {medication.name} entrou no seu acompanhamento.')
        else:
            messages.success(self.request, 'Tudo pronto. Seu peso entrou no histórico.')
        return redirect('core:dashboard')
