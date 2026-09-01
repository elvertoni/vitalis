"""
Thin client for the Evolution API, the WhatsApp gateway that already runs on the same VPS.

``urllib`` on purpose, no SDK: one endpoint is used (send a text message), and the project
has no HTTP client dependency — ``billing.services`` talks to Mercado Pago the same way.

Configuration comes from the environment, like everything else here. With
``EVOLUTION_API_URL``/``_KEY``/``_INSTANCE`` unset the client reports itself as unconfigured
and ``lembretes.notifications`` quietly keeps using e-mail, so a missing variable degrades
into the old behaviour instead of losing a reminder.

The instance is a *separate* one named ``vitalis``: the same gateway also serves a clinic and
other projects, and personal health notices have no business sharing a WhatsApp session with
them (D-045).
"""

import json
import re
import urllib.error
import urllib.request

from django.conf import settings

TIMEOUT_SECONDS = 15
BRAZIL_COUNTRY_CODE = '55'


class WhatsAppError(Exception):
    """Gateway refused the message, or was unreachable."""


def is_configured():
    return bool(settings.EVOLUTION_API_URL and settings.EVOLUTION_API_KEY and settings.EVOLUTION_INSTANCE)


def normalize_phone(raw):
    """
    Turns what a person typed into the digits-only form the gateway expects.

    ``(41) 99115-8701`` becomes ``5541991158701``. Returns ``None`` when what is stored
    cannot be a phone number, so the caller falls back to e-mail instead of asking the
    gateway to deliver into the void.
    """
    digits = re.sub(r'\D', '', raw or '')
    if not digits:
        return None
    if not digits.startswith(BRAZIL_COUNTRY_CODE):
        digits = BRAZIL_COUNTRY_CODE + digits
    # 55 + DDD (2) + número (8 ou 9). Fora dessa faixa é engano de digitação, não telefone.
    if not 12 <= len(digits) <= 13:
        return None
    return digits


def send_text(phone, message):
    """Sends one text message. Raises ``WhatsAppError`` — never swallows a failure."""
    if not is_configured():
        raise WhatsAppError('Evolution API não configurada (EVOLUTION_API_URL/_KEY/_INSTANCE).')
    number = normalize_phone(phone)
    if number is None:
        raise WhatsAppError(f'Telefone inválido para envio: {phone!r}')

    url = f'{settings.EVOLUTION_API_URL}/message/sendText/{settings.EVOLUTION_INSTANCE}'
    payload = json.dumps({'number': number, 'text': message}).encode('utf-8')
    request = urllib.request.Request(
        url,
        data=payload,
        headers={'Content-Type': 'application/json', 'apikey': settings.EVOLUTION_API_KEY},
        method='POST',
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='replace')[:300]
        raise WhatsAppError(f'HTTP {exc.code} do gateway: {detail}') from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise WhatsAppError(f'Falha ao falar com o gateway: {exc}') from exc
