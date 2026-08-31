from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Profile, User


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'perfil'


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin rebuilt around the email login: there is no username field."""

    inlines = [ProfileInline]
    list_display = ['email', 'full_name', 'is_active', 'is_staff', 'date_joined']
    list_filter = ['is_active', 'is_staff', 'is_superuser']
    search_fields = ['email', 'full_name']
    ordering = ['email']
    readonly_fields = ['date_joined', 'last_login', 'created_at', 'updated_at']
    fieldsets = [
        (None, {'fields': ['email', 'password']}),
        ('Dados pessoais', {'fields': ['full_name']}),
        ('Permissões', {'fields': ['is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions']}),
        ('Datas', {'fields': ['last_login', 'date_joined', 'created_at', 'updated_at']}),
    ]
    add_fieldsets = [
        (None, {
            'classes': ['wide'],
            'fields': ['email', 'full_name', 'usable_password', 'password1', 'password2'],
        }),
    ]
