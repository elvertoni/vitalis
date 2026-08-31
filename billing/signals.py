"""Every new account starts on the Free plan — PRD 4.3, onboarding step 5."""

from django.db.models.signals import post_save
from django.dispatch import receiver

from accounts.models import User

from .models import Plan, Subscription


@receiver(post_save, sender=User)
def create_free_subscription(sender, instance, created, **kwargs):
    if not created:
        return
    free_plan = Plan.objects.filter(slug='free').first()
    if free_plan is None:
        return  # banco ainda sem seed dos planos (ex.: primeira migração rodando); nada a fazer
    Subscription.objects.create(user=instance, plan=free_plan, status=Subscription.Status.ACTIVE)
