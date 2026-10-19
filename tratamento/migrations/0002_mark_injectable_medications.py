"""Marks as injectable every medication that already has a shot on record (D-071)."""

from django.db import migrations


def mark_injectables(apps, schema_editor):
    Injection = apps.get_model('tratamento', 'Injection')
    Medication = apps.get_model('saude', 'Medication')
    ids = Injection.objects.values_list('medication_id', flat=True).distinct()
    Medication.objects.filter(pk__in=list(ids)).update(is_injectable=True)


class Migration(migrations.Migration):

    dependencies = [
        ('saude', '0007_medication_is_injectable'),
        ('tratamento', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(mark_injectables, migrations.RunPython.noop),
    ]
