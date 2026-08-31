"""
SaaS layer: plans, subscriptions, and the feature gate the rest of the app reads.

``Plan`` is the one genuinely shared, non-owned model in this codebase — everyone reads the
same two rows (Free, Premium). ``Subscription`` belongs to a user like everything else, so it
follows the usual ``OwnedModel`` pattern.
"""

from django.db import models
from django.urls import reverse
from django.utils import timezone

from core.models import OwnedModel, TimeStampedModel


class Plan(TimeStampedModel):
    """
    A purchasable tier. Not owned by anyone — see ``core.models.OwnedModel`` for the
    isolation pattern this deliberately does not use.

    ``slug`` is what code checks against (``plan.slug == 'premium'``); ``name`` is just the
    label shown on screen, free to rename without touching a single gating rule.
    """

    class BillingPeriod(models.TextChoices):
        MONTHLY = 'monthly', 'Mensal'
        YEARLY = 'yearly', 'Anual'

    slug = models.SlugField('identificador', unique=True)
    name = models.CharField('nome', max_length=60)
    price = models.DecimalField('preço', max_digits=8, decimal_places=2, default=0)
    billing_period = models.CharField(
        'periodicidade', max_length=10, choices=BillingPeriod.choices, default=BillingPeriod.MONTHLY,
    )
    limits = models.JSONField(
        'limites', default=dict, blank=True,
        help_text='Ex.: {"active_diets": 1, "auto_reminders": false, "ai_enabled": false}. Vazio = sem limite.',
    )
    is_active = models.BooleanField('disponível para assinatura', default=True)

    class Meta:
        verbose_name = 'plano'
        verbose_name_plural = 'planos'
        ordering = ['price']

    def __str__(self):
        return self.name

    def limit(self, key, default=None):
        return self.limits.get(key, default)


class Subscription(OwnedModel):
    """
    A user's billing history. Several rows can exist over time (trial → cancelada → nova);
    only one may be currently open (``trial``/``active``/``past_due``) — enforced below, the
    same partial-uniqueness pattern ``_legado_vida`` used for a live ``Compartilhamento``.
    """

    class Status(models.TextChoices):
        TRIAL = 'trial', 'Teste'
        ACTIVE = 'active', 'Ativa'
        CANCELLED = 'cancelled', 'Cancelada'
        PAST_DUE = 'past_due', 'Inadimplente'

    # Plano é catálogo compartilhado, não dado do dono: PROTECT aqui é o caso legítimo que
    # D-021 não é — apagar um Plano com assinantes tem que travar; a cascata de exclusão de
    # um usuário nunca precisa atravessar Plan (ela para em Subscription, que é CASCADE a
    # partir de user).
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name='subscriptions', verbose_name='plano')
    status = models.CharField('situação', max_length=10, choices=Status.choices, default=Status.TRIAL)
    started_at = models.DateTimeField('início', default=timezone.now)
    expires_at = models.DateTimeField('expira em', null=True, blank=True)
    gateway_customer_id = models.CharField('id do cliente no gateway', max_length=120, blank=True)
    gateway_subscription_id = models.CharField('id da assinatura no gateway', max_length=120, blank=True)

    class Meta:
        verbose_name = 'assinatura'
        verbose_name_plural = 'assinaturas'
        ordering = ['-started_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user'],
                condition=models.Q(status__in=['trial', 'active', 'past_due']),
                name='uma_assinatura_corrente_por_usuario',
            ),
        ]

    def __str__(self):
        return f'{self.user} · {self.plan} ({self.get_status_display()})'

    def get_absolute_url(self):
        return reverse('billing:subscription')

    @property
    def is_open(self):
        return self.status in {self.Status.TRIAL, self.Status.ACTIVE, self.Status.PAST_DUE}


def current_subscription(user):
    """The one open row, or ``None`` — a user between plans (rare: only right after a manual DB edit)."""
    return Subscription.objects.filter(
        user=user, status__in=[Subscription.Status.TRIAL, Subscription.Status.ACTIVE, Subscription.Status.PAST_DUE],
    ).select_related('plan').first()


def current_plan(user):
    """The plan gating reads. Falls back to the Free plan if, somehow, there is no open subscription."""
    subscription = current_subscription(user)
    if subscription:
        return subscription.plan
    return Plan.objects.filter(slug='free').first()


def limit_for(user, key, default=None):
    plan = current_plan(user)
    return plan.limit(key, default) if plan else default
