from django.contrib import admin

from .models import Reminder


@admin.register(Reminder)
class ReminderAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'category', 'status', 'remind_at', 'is_recurring']
    list_filter = ['category', 'status', 'is_recurring']
    search_fields = ['title', 'user__email']
    readonly_fields = ['content_type', 'object_id', 'sent_at']
