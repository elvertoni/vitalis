"""
Payment gateway boundary — PRD 10.3: "isolar a integração num serviço para trocar de
gateway sem espalhar código." Everything outside this module talks to ``get_gateway()``
and the two methods below, never to Mercado Pago's API shape directly.

``MercadoPagoGateway`` calls the real Checkout Pro REST API (``/checkout/preferences``) with
the stdlib's ``urllib`` — no SDK dependency added for one HTTP call. It needs
``MERCADOPAGO_ACCESS_TOKEN`` in the environment to do anything; without it, every method
raises ``GatewayNotConfigured`` instead of pretending to work. There is no real seller
account behind this build, so the integration has the correct shape (preference creation,
back_urls, webhook-ready) but has never been exercised against a live payment — going to
production needs a real Mercado Pago access token and a public webhook URL, nothing else.
"""

import json
import os
import urllib.error
import urllib.request

API_BASE = 'https://api.mercadopago.com'


class GatewayNotConfigured(Exception):
    """Raised instead of silently no-opping, so a misconfigured deploy fails loud, not quiet."""


class GatewayError(Exception):
    """The gateway responded, but with an error — surfaced to the view as a flash message."""


class PaymentGateway:
    """The interface the rest of the app is written against."""

    def start_checkout(self, subscription, success_url, failure_url):
        """Returns the URL to redirect the person to in order to pay."""
        raise NotImplementedError

    def cancel(self, subscription):
        """Cancels the recurring charge on the gateway side."""
        raise NotImplementedError


class MercadoPagoGateway(PaymentGateway):
    def __init__(self):
        self.access_token = os.environ.get('MERCADOPAGO_ACCESS_TOKEN', '')

    def _require_token(self):
        if not self.access_token:
            raise GatewayNotConfigured(
                'MERCADOPAGO_ACCESS_TOKEN não definido. Configure a variável de ambiente '
                'com o access token de produção ou de teste da conta Mercado Pago.'
            )

    def _request(self, method, path, payload=None):
        self._require_token()
        request = urllib.request.Request(
            f'{API_BASE}{path}',
            method=method,
            data=json.dumps(payload).encode('utf-8') if payload is not None else None,
            headers={
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json',
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as error:
            body = error.read().decode('utf-8', errors='replace')
            raise GatewayError(f'Mercado Pago respondeu {error.code}: {body}') from error
        except urllib.error.URLError as error:
            raise GatewayError(f'Não foi possível falar com o Mercado Pago: {error.reason}') from error

    def start_checkout(self, subscription, success_url, failure_url):
        plan = subscription.plan
        preference = self._request('POST', '/checkout/preferences', {
            'items': [{
                'title': f'Vitalis · {plan.name}',
                'quantity': 1,
                'currency_id': 'BRL',
                'unit_price': float(plan.price),
            }],
            'payer': {'email': subscription.user.email},
            'back_urls': {'success': success_url, 'failure': failure_url, 'pending': failure_url},
            'auto_return': 'approved',
            'external_reference': str(subscription.pk),
            # Pix + cartão: recomendação do PRD para público brasileiro. Sem excluir nada,
            # o Checkout Pro já oferece os dois por padrão quando a conta os tem habilitados.
        })
        return preference['init_point']

    def cancel(self, subscription):
        if not subscription.gateway_subscription_id:
            return  # nunca chegou a ter cobrança recorrente no gateway; nada a cancelar lá
        self._request('PUT', f'/preapproval/{subscription.gateway_subscription_id}', {'status': 'cancelled'})

    def get_payment(self, payment_id):
        """Used by the webhook to look up what a notification is actually reporting."""
        return self._request('GET', f'/v1/payments/{payment_id}')


def get_gateway():
    """Single seam to swap gateways — the only line every other module should import."""
    return MercadoPagoGateway()
