from django.contrib import admin

from .models import Injection, SideEffect


@admin.register(Injection)
class InjectionAdmin(admin.ModelAdmin):
    list_display = ['medication', 'dose_mg', 'site', 'applied_at', 'user']
    list_filter = ['site']
    search_fields = ['medication__name', 'user__email']
    date_hierarchy = 'applied_at'


@admin.register(SideEffect)
class SideEffectAdmin(admin.ModelAdmin):
    list_display = ['kind', 'intensity', 'date', 'injection', 'user']
    list_filter = ['kind', 'intensity']
    search_fields = ['user__email']
    date_hierarchy = 'date'
