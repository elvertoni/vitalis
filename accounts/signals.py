"""Signal handlers for the accounts app. Registered in ``AccountsConfig.ready()``."""

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Profile, User


@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    """Guarantees ``user.profile`` exists from the moment the account is created."""
    if created:
        Profile.objects.create(user=instance)
