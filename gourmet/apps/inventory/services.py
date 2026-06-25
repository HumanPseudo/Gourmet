from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from django.db.models import F, QuerySet
from django.shortcuts import get_object_or_404

from gourmet.apps.menu.models import Product

from .models import InventoryItem, InventoryMovement, ProductRecipe


class InventoryService:
    @staticmethod
    def list_items() -> QuerySet[InventoryItem]:
        return InventoryItem.objects.all()

    @staticmethod
    def get_item(item_id: UUID) -> InventoryItem:
        return get_object_or_404(InventoryItem, pk=item_id)

    @staticmethod
    def create_item(
        name: str, unit: str, stock: Decimal, min_stock: Decimal,
        cost_price: Decimal | None,
    ) -> InventoryItem:
        return InventoryItem.objects.create(
            name=name, unit=unit, stock=stock, min_stock=min_stock,
            cost_price=cost_price,
        )

    @staticmethod
    def update_item(
        item_id: UUID,
        name: str,
        unit: str,
        stock: Decimal,
        min_stock: Decimal,
        cost_price: Decimal | None,
    ) -> InventoryItem:
        item = get_object_or_404(InventoryItem, pk=item_id)
        item.name = name
        item.unit = unit
        item.stock = stock
        item.min_stock = min_stock
        item.cost_price = cost_price
        item.save()
        return item

    @staticmethod
    def delete_item(item_id: UUID) -> None:
        item = get_object_or_404(InventoryItem, pk=item_id)
        item.delete()

    @staticmethod
    def low_stock_items() -> QuerySet[InventoryItem]:
        return InventoryItem.objects.filter(stock__lte=F("min_stock"))

    @staticmethod
    def list_recipes() -> QuerySet[ProductRecipe]:
        return ProductRecipe.objects.select_related("product", "item").all()

    @staticmethod
    def get_recipe(recipe_id: UUID) -> ProductRecipe:
        return get_object_or_404(
            ProductRecipe.objects.select_related("product", "item"),
            pk=recipe_id,
        )

    @staticmethod
    def create_recipe(
        product_id: UUID, item_id: UUID, quantity: Decimal
    ) -> ProductRecipe:
        product = get_object_or_404(Product, pk=product_id)
        item = get_object_or_404(InventoryItem, pk=item_id)
        return ProductRecipe.objects.create(
            product=product, item=item, quantity=quantity
        )

    @staticmethod
    def delete_recipe(recipe_id: UUID) -> None:
        recipe = get_object_or_404(ProductRecipe, pk=recipe_id)
        recipe.delete()

    @staticmethod
    def list_movements(
        item_id: UUID | None = None,
    ) -> QuerySet[InventoryMovement]:
        qs = InventoryMovement.objects.select_related("item").all()
        if item_id:
            qs = qs.filter(item_id=item_id)
        return qs
