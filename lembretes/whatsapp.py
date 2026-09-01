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

# O gateway pode estar atrás de um proxy que barra cliente sem identidade: o Cloudflare
# devolve 403 "error code: 1010" para o User-Agent padrão do urllib. Identificar-se resolve,
# e é o que qualquer cliente educado faz.
USER_AGENT = 'Vitalis/1.0 (+https://vitalis.tonicoimbra.com)'


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


def _call(method, path, payload=None):
    """One request to the gateway. Raises ``WhatsAppError`` — never swallows a failure."""
    if not is_configured():
        raise WhatsAppError('Evolution API não configurada (EVOLUTION_API_URL/_KEY/_INSTANCE).')
    request = urllib.request.Request(
        f'{settings.EVOLUTION_API_URL}{path}',
        data=json.dumps(payload).encode('utf-8') if payload is not None else None,
        headers={
            'Content-Type': 'application/json',
            'apikey': settings.EVOLUTION_API_KEY,
            'User-Agent': USER_AGENT,
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            body = response.read().decode('utf-8')
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='replace')[:300]
        raise WhatsAppError(f'HTTP {exc.code} do gateway: {detail}') from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise WhatsAppError(f'Falha ao falar com o gateway: {exc}') from exc


def send_text(phone, message):
    """Sends one text message to a phone number."""
    number = normalize_phone(phone)
    if number is None:
        raise WhatsAppError(f'Telefone inválido para envio: {phone!r}')
    instance = settings.EVOLUTION_INSTANCE
    return _call('POST', f'/message/sendText/{instance}', {'number': number, 'text': message})


def connection_state():
    """``'open'`` when the session is live, ``'connecting'`` while waiting for the QR scan."""
    data = _call('GET', f'/instance/connectionState/{settings.EVOLUTION_INSTANCE}')
    return (data.get('instance') or {}).get('state', 'unknown')


def connect():
    """
    Asks for a fresh pairing QR. Returns ``(base64_image, pairing_code)``.

    The gateway regenerates the code on every call and each one lives well under a minute,
    so the panel refetches instead of caching: a stale QR is a dead end for whoever is
    holding a phone in front of the screen.
    """
    data = _call('GET', f'/instance/connect/{settings.EVOLUTION_INSTANCE}')
    payload = data.get('qrcode') or data
    return payload.get('base64'), payload.get('pairingCode') or payload.get('code')


def connected_number():
    """The phone number the live session belongs to, or ``None`` when disconnected."""
    instance = settings.EVOLUTION_INSTANCE
    data = _call('GET', f'/instance/fetchInstances?instanceName={instance}')
    items = data if isinstance(data, list) else [data]
    for item in items:
        info = item.get('instance', item)
        if info.get('name') == instance or info.get('instanceName') == instance:
            owner = info.get('ownerJid') or info.get('owner') or ''
            return owner.split('@')[0] or None
    return None


def logout():
    """Drops the session. The phone stops being the sender until someone scans again."""
    return _call('DELETE', f'/instance/logout/{settings.EVOLUTION_INSTANCE}')
