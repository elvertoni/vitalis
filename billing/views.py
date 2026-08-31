"""
Subscription management. Every view here reads/writes only the logged-in user's own
``Subscription`` — the FK is the isolation, same guarantee as ``OwnerQuerySetMixin`` gives
everywhere else, just expressed directly since there is exactly one object per user to find,
not a list.
"""

import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, HttpResponseNotAllowed
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView

from .models import Plan, Subscription, current_subscription
from .services import GatewayError, GatewayNotConfigured, get_gateway

logger = logging.getLogger(__name__)


class SubscriptionView(LoginRequiredMixin, TemplateView):
    """'Minha assinatura': the plan comparison plus the current status, per PRD 12."""

    template_name = 'billing/subscription.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['subscription'] = current_subscription(self.request.user)
        context['plans'] = Plan.objects.filter(is_active=True)
        context['gateway_configured'] = bool(get_gateway().access_token)
        return context


class SubscribeView(LoginRequiredMixin, View):
    """Starts checkout for a plan. GET only reachable through the button on the page above."""

    def post(self, request, slug):
        plan = Plan.objects.filter(slug=slug, is_active=True).first()
        if plan is None:
            messages.error(request, 'Plano não encontrado.')
            return redirect('billing:subscription')

        existing = current_subscription(request.user)
        if existing and existing.plan_id == plan.pk and existing.status == Subscription.Status.ACTIVE:
            messages.info(request, 'Você já está neste plano.')
            return redirect('billing:subscription')

        if plan.price == 0:
            # Sem cobrança: troca de plano é só um registro, não passa pelo gateway.
            if existing:
                existing.status = Subscription.Status.CANCELLED
                existing.save(update_fields=['status', 'updated_at'])
            Subscription.objects.create(user=request.user, plan=plan, status=Subscription.Status.ACTIVE)
            messages.success(request, f'Você está no plano {plan.name}.')
            return redirect('billing:subscription')

        # A constraint de "uma assinatura corrente" é por usuário, não por usuário+plano —
        # só pode haver UMA linha aberta (trial/active/past_due) de cada vez. Reaproveita um
        # trial pendente do mesmo plano (retry de checkout); fecha qualquer outra antes de
        # abrir uma nova, senão o create() abaixo estoura IntegrityError.
        if existing and existing.plan_id == plan.pk and existing.status == Subscription.Status.TRIAL:
            subscription = existing
        else:
            if existing:
                existing.status = Subscription.Status.CANCELLED
                existing.save(update_fields=['status', 'updated_at'])
            subscription = Subscription.objects.create(user=request.user, plan=plan, status=Subscription.Status.TRIAL)

        try:
            checkout_url = get_gateway().start_checkout(
                subscription,
                success_url=request.build_absolute_uri(reverse('billing:subscription')),
                failure_url=request.build_absolute_uri(reverse('billing:subscription')),
            )
        except GatewayNotConfigured as error:
            messages.warning(
                request,
                'Pagamento ainda não está configurado neste ambiente. '
                'Em desenvolvimento, use o botão de ativação de teste abaixo.' if settings.DEBUG else
                'Assinaturas estão temporariamente indisponíveis. Tente novamente mais tarde.',
            )
            logger.warning('Checkout indisponível: %s', error)
            return redirect('billing:subscription')
        except GatewayError as error:
            messages.error(request, 'Não foi possível iniciar o pagamento. Tente novamente em instantes.')
            logger.exception('Falha ao criar checkout no Mercado Pago: %s', error)
            return redirect('billing:subscription')

        return redirect(checkout_url)


class CancelSubscriptionView(LoginRequiredMixin, View):
    def post(self, request):
        subscription = current_subscription(request.user)
        if subscription is None or subscription.plan.price == 0:
            messages.info(request, 'Não há assinatura paga para cancelar.')
            return redirect('billing:subscription')

        try:
            get_gateway().cancel(subscription)
        except (GatewayNotConfigured, GatewayError) as error:
            logger.warning('Cancelamento no gateway não concluído: %s', error)

        subscription.status = Subscription.Status.CANCELLED
        subscription.save(update_fields=['status', 'updated_at'])
        free_plan = Plan.objects.filter(slug='free').first()
        if free_plan:
            Subscription.objects.create(user=request.user, plan=free_plan, status=Subscription.Status.ACTIVE)
        messages.success(request, 'Assinatura cancelada. Você voltou para o plano Free.')
        return redirect('billing:subscription')


class DevActivateSubscriptionView(LoginRequiredMixin, View):
    """
    Marks the pending premium subscription active without a real charge.

    Only reachable with ``DEBUG=True`` — this is a local-testing shortcut, not a payment
    method, because there is no real Mercado Pago account behind this build to test
    against. Never available once ``DEBUG=False``.
    """

    def post(self, request):
        if not settings.DEBUG:
            return HttpResponseNotAllowed(['POST'])
        subscription = Subscription.objects.filter(
            user=request.user, status=Subscription.Status.TRIAL,
        ).order_by('-started_at').first()
        if subscription is None:
            messages.error(request, 'Nenhuma assinatura pendente para ativar.')
            return redirect('billing:subscription')
        subscription.status = Subscription.Status.ACTIVE
        subscription.save(update_fields=['status', 'updated_at'])
        messages.success(request, f'[Ambiente de teste] Assinatura do plano {subscription.plan.name} ativada sem cobrança real.')
        return redirect('billing:subscription')


@method_decorator(csrf_exempt, name='dispatch')
class MercadoPagoWebhookView(View):
    """
    Receives Mercado Pago's payment notifications (IPN/webhooks).

    Always answers 200 quickly — Mercado Pago retries aggressively on anything else, and a
    slow or failing handler here should never look, from their side, like something worth
    hammering. Errors are logged, not raised. Untested against a real notification (no
    seller account configured), but the shape follows Mercado Pago's documented payload.
    """

    def post(self, request):
        topic = request.GET.get('type') or request.GET.get('topic')
        payment_id = request.GET.get('data.id') or request.GET.get('id')
        if topic != 'payment' or not payment_id:
            return HttpResponse(status=200)

        try:
            payment = get_gateway().get_payment(payment_id)
        except (GatewayNotConfigured, GatewayError) as error:
            logger.warning('Não foi possível consultar pagamento %s: %s', payment_id, error)
            return HttpResponse(status=200)

        subscription_id = payment.get('external_reference')
        status = payment.get('status')
        subscription = Subscription.objects.filter(pk=subscription_id).first()
        if subscription is None:
            logger.warning('Webhook do Mercado Pago referenciou assinatura inexistente: %s', subscription_id)
            return HttpResponse(status=200)

        if status == 'approved':
            subscription.status = Subscription.Status.ACTIVE
            subscription.gateway_customer_id = payment.get('payer', {}).get('id', '') or subscription.gateway_customer_id
        elif status in {'rejected', 'cancelled'}:
            subscription.status = Subscription.Status.CANCELLED
        elif status == 'in_process':
            subscription.status = Subscription.Status.PAST_DUE
        subscription.save(update_fields=['status', 'gateway_customer_id', 'updated_at'])
        return HttpResponse(status=200)
