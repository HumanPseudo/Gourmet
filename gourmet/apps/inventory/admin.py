from django.contrib import admin

from .models import InventoryItem, InventoryMovement, ProductRecipe


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin[InventoryItem]):
    list_display = ("name", "unit", "stock", "min_stock", "cost_price")
    list_filter = ("unit",)
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(ProductRecipe)
class ProductRecipeAdmin(admin.ModelAdmin[ProductRecipe]):
    list_display = ("product", "item", "quantity")
    search_fields = ("product__name", "item__name")
    ordering = ("product__name", "item__name")


@admin.register(InventoryMovement)
class InventoryMovementAdmin(admin.ModelAdmin[InventoryMovement]):
    list_display = ("item", "type", "quantity", "reference", "created_at")
    list_filter = ("type",)
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
