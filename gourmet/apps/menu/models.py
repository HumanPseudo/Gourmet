from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from django.db import models


class Category(models.Model):
    id: models.UUIDField[uuid.UUID, uuid.UUID] = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    name: models.CharField[str, str] = models.CharField(
        max_length=100, unique=True, verbose_name="Name"
    )
    description: models.TextField[str | None, str | None] = models.TextField(
        blank=True, null=True, verbose_name="Description"
    )
    sort_order: models.IntegerField[int, int] = models.IntegerField(
        default=0, verbose_name="Order"
    )
    is_active: models.BooleanField[bool, bool] = models.BooleanField(
        default=True, verbose_name="Active"
    )
    created_at: models.DateTimeField[Any, Any] = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField[Any, Any] = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name


class Product(models.Model):
    id: models.UUIDField[uuid.UUID, uuid.UUID] = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    category: models.ForeignKey[Category, Category] = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="products",
        verbose_name="Category",
    )
    category_id: uuid.UUID
    name: models.CharField[str, str] = models.CharField(
        max_length=200, verbose_name="Name"
    )
    description: models.TextField[str | None, str | None] = models.TextField(
        blank=True, null=True, verbose_name="Description"
    )
    price: models.DecimalField[Decimal, Decimal] = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Price"
    )
    is_available: models.BooleanField[bool, bool] = models.BooleanField(
        default=True, verbose_name="Available"
    )
    sort_order: models.IntegerField[int, int] = models.IntegerField(
        default=0, verbose_name="Order"
    )
    created_at: models.DateTimeField[Any, Any] = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField[Any, Any] = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Product"
        verbose_name_plural = "Products"
        ordering = ["category__sort_order", "sort_order", "name"]

    def __str__(self) -> str:
        return self.name
