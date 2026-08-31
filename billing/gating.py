"""
Where a plan's ``limits`` JSON turns into an actual rule some other app enforces.

Kept separate from ``billing.models`` on purpose: this module imports ``nutricao``, which
would make ``billing.models`` depend on an app that itself might reasonably want to import
``billing`` back one day (a diet page showing "upgrade for more"). Views import from here,
never the other way around.
"""

from .models import limit_for


def diet_limit_exceeded(user, excluding_pk=None):
    """True when activating one more diet would break the plan's ``active_diets`` limit."""
    limit = limit_for(user, 'active_diets')
    if limit is None:
        return False
    from nutricao.models import Diet

    queryset = Diet.objects.filter(user=user, is_active=True)
    if excluding_pk is not None:
        queryset = queryset.exclude(pk=excluding_pk)
    return queryset.count() >= limit


def auto_reminders_enabled(user):
    """False on a plan whose ``limits`` explicitly turns automatic reminders off."""
    return bool(limit_for(user, 'auto_reminders', default=True))
