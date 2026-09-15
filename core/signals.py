"""
A sensitive file leaves the disk together with its row.

Django deletes the row behind a FileField and leaves the file behind: deleting an exam, swapping
the report while editing it, or deleting an account (CASCADE) would strand lab reports and
prescriptions on the media volume. The receivers below cover every model with a FileField —
connected once in ``CoreConfig.ready`` — and remove the file only after the transaction commits,
so a rollback never loses a file whose row survived.
"""

from django.db import models, transaction


def file_fields(model):
    return [field for field in model._meta.concrete_fields if isinstance(field, models.FileField)]


def _delete_after_commit(field_file):
    name, storage = field_file.name, field_file.storage
    if name:
        transaction.on_commit(lambda: storage.delete(name))


def delete_files_with_row(sender, instance, **kwargs):
    for field in file_fields(sender):
        _delete_after_commit(getattr(instance, field.name))


def delete_replaced_files(sender, instance, raw=False, **kwargs):
    # Fixture e registro novo não têm arquivo anterior a comparar.
    if raw or instance._state.adding or not instance.pk:
        return
    fields = file_fields(sender)
    previous = sender._base_manager.filter(pk=instance.pk).only(*[f.name for f in fields]).first()
    if previous is None:
        return
    for field in fields:
        old = getattr(previous, field.name)
        new = getattr(instance, field.name)
        if old and old.name != (new.name if new else None):
            _delete_after_commit(old)


def connect_file_cleanup():
    from django.apps import apps
    from django.db.models.signals import post_delete, pre_save

    for model in apps.get_models():
        if not file_fields(model):
            continue
        label = model._meta.label
        post_delete.connect(delete_files_with_row, sender=model, dispatch_uid=f'files-delete:{label}')
        pre_save.connect(delete_replaced_files, sender=model, dispatch_uid=f'files-replace:{label}')
