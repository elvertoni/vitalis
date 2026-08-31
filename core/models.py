"""Abstract base models shared by every domain app."""

from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    """Adds creation and update timestamps. Every domain model inherits from this."""

    created_at = models.DateTimeField('criado em', auto_now_add=True)
    updated_at = models.DateTimeField('atualizado em', auto_now=True)

    class Meta:
        abstract = True


class OwnedModel(TimeStampedModel):
    """
    Adds the mandatory owner foreign key.

    Data isolation depends on this column: every domain queryset is filtered by it
    through ``OwnerQuerySetMixin``. A model holding user data without this base class
    would escape the isolation layer.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='%(app_label)s_%(class)s_set',
        verbose_name='usuário',
    )

    class Meta:
        abstract = True
