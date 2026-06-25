from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from django.db import models

if TYPE_CHECKING:
    from gourmet.apps.menu.models import Product


class InventoryItem(models.Model):
    id: models.UUIDField[uuid.UUID, uuid.UUID] = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    name: models.CharField[str, str] = models.CharField(
        max_length=200, unique=True
    )
    unit: models.CharField[str, str] = models.CharField(
        max_length=20, verbose_name="Unit (kg, unit, liter, pack)"
    )
    stock: models.DecimalField[Decimal, Decimal] = models.DecimalField(
        max_digits=10, decimal_places=3, default=Decimal("0.000")
    )
    min_stock: models.DecimalField[Decimal, Decimal] = models.DecimalField(
        max_digits=10, decimal_places=3, default=Decimal("0.000")
    )
    cost_price: models.DecimalField[Decimal | None, Decimal | None] = (
        models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    )
    created_at: models.DateTimeField[Any, Any] = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField[Any, Any] = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "inventory items"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class ProductRecipe(models.Model):
    id: models.UUIDField[uuid.UUID, uuid.UUID] = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    product: models.ForeignKey[Product, Product] = models.ForeignKey(
        "menu.Product", on_delete=models.CASCADE, related_name="recipes"
    )
    item: models.ForeignKey[InventoryItem, InventoryItem] = models.ForeignKey(
        InventoryItem, on_delete=models.CASCADE, related_name="recipes"
    )
    quantity: models.DecimalField[Decimal, Decimal] = models.DecimalField(
        max_digits=10, decimal_places=3
    )

    class Meta:
        unique_together = [("product", "item")]
        ordering = ["product__name", "item__name"]

    def __str__(self) -> str:
        return f"{self.product.name} → {self.item.name} x{self.quantity}"


class InventoryMovement(models.Model):
    class Type(models.TextChoices):
        IN = "in", "In"
        OUT = "out", "Out"

    id: models.UUIDField[uuid.UUID, uuid.UUID] = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    item: models.ForeignKey[InventoryItem, InventoryItem] = models.ForeignKey(
        InventoryItem, on_delete=models.CASCADE, related_name="movements"
    )
    type: models.CharField[str, str] = models.CharField(
        max_length=8, choices=Type.choices
    )
    quantity: models.DecimalField[Decimal, Decimal] = models.DecimalField(
        max_digits=10, decimal_places=3
    )
    reference: models.CharField[str, str] = models.CharField(
        max_length=100, blank=True
    )
    created_at: models.DateTimeField[Any, Any] = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.type} {self.item.name} x{self.quantity}"
