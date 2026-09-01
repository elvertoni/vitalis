"""
Lightweight in-memory rate limiting based on Django's cache framework.
Used to protect brute-force sensitive endpoints (login, password reset).
"""

import time
from django.core.cache import cache


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '127.0.0.1')


def is_rate_limited(key, max_requests=5, window_seconds=60):
    """
    Checks whether `key` has exceeded `max_requests` in `window_seconds`.
    Returns True if rate limited (blocked), False otherwise.
    """
    cache_key = f'ratelimit:{key}'
    requests = cache.get(cache_key, [])
    now = time.time()
    valid_requests = [t for t in requests if now - t < window_seconds]
    if len(valid_requests) >= max_requests:
        return True
    valid_requests.append(now)
    cache.set(cache_key, valid_requests, timeout=window_seconds)
    return False
