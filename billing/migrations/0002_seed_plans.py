"""
Seeds the two plans from PRD 10.2.

Premium's price was marked "⚠️ definir" in the PRD, with no recommendation anywhere else in
the document. Decided here as a placeholder under the ambiguity protocol — see D-031 in
DECISIONS.md — and deliberately kept as data, not code: change it from the admin at any time,
no migration or deploy needed.
"""

from decimal import Decimal

from django.db import migrations


def seed_plans(apps, schema_editor):
    Plan = apps.get_model('billing', 'Plan')
    Plan.objects.update_or_create(
        slug='free',
        defaults=dict(
            name='Free',
            price=Decimal('0'),
            billing_period='monthly',
            limits={'active_diets': 1, 'auto_reminders': False, 'ai_enabled': False},
            is_active=True,
        ),
    )
    Plan.objects.update_or_create(
        slug='premium',
        defaults=dict(
            name='Premium',
            price=Decimal('29.90'),
            billing_period='monthly',
            limits={'active_diets': None, 'auto_reminders': True, 'ai_enabled': False},
            is_active=True,
        ),
    )


def remove_plans(apps, schema_editor):
    Plan = apps.get_model('billing', 'Plan')
    Plan.objects.filter(slug__in=['free', 'premium']).delete()


class Migration(migrations.Migration):
    dependencies = [('billing', '0001_initial')]

    operations = [migrations.RunPython(seed_plans, remove_plans)]
