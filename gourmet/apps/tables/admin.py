from django.contrib import admin

from .models import Table, TableLayout, TableLayoutItem


@admin.register(Table)
class TableAdmin(admin.ModelAdmin[Table]):
    list_display = ("code", "capacity", "status", "is_active", "updated_at")
    list_filter = ("status", "is_active")
    search_fields = ("code",)
    ordering = ("code",)


class TableLayoutItemInline(admin.TabularInline[TableLayoutItem, TableLayout]):
    model = TableLayoutItem
    extra = 0


@admin.register(TableLayout)
class TableLayoutAdmin(admin.ModelAdmin[TableLayout]):
    list_display = ("name", "width", "height", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name",)
    ordering = ("name",)
    inlines = [TableLayoutItemInline]
