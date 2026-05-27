from django.contrib import admin

from .models import Category, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin[Category]):
    list_display = ("name", "sort_order", "is_active")
    list_editable = ("sort_order", "is_active")
    search_fields = ("name",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin[Product]):
    list_display = ("name", "category", "price", "is_available", "sort_order")
    list_editable = ("price", "is_available", "sort_order")
    list_filter = ("category", "is_available")
    search_fields = ("name", "description")
