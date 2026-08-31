from django.contrib import admin

from .models import Plan, Subscription


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'price', 'billing_period', 'is_active']
    list_filter = ['billing_period', 'is_active']
    prepopulated_fields = {'slug': ['name']}


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['user', 'plan', 'status', 'started_at', 'expires_at']
    list_filter = ['status', 'plan']
    search_fields = ['user__email', 'gateway_customer_id', 'gateway_subscription_id']
    readonly_fields = ['gateway_customer_id', 'gateway_subscription_id']
