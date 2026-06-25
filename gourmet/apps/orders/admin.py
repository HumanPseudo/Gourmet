from django.contrib import admin

from .models import Order, OrderItem, Payment


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin[Order]):
    list_display = ("id", "table", "status", "total", "created_at")
    list_filter = ("status",)
    search_fields = ("id",)
    date_hierarchy = "created_at"
    ordering = ("-created_at",)


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin[OrderItem]):
    list_display = ("product_name", "order", "quantity", "status")
    list_filter = ("status",)
    search_fields = ("product_name",)
    ordering = ("created_at",)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin[Payment]):
    list_display = ("order", "method", "amount", "created_at")
    list_filter = ("method",)
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
