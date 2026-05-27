from django.contrib import admin

from .models import Table


@admin.register(Table)
class TableAdmin(admin.ModelAdmin[Table]):
    list_display = ("code", "capacity", "status", "is_active", "updated_at")
    list_filter = ("status", "is_active")
    search_fields = ("code",)
    ordering = ("code",)
