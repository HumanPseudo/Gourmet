from __future__ import annotations

import uuid
from typing import Any

from django.db import models


class Table(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        OCCUPIED = "occupied", "Occupied"
        RESERVED = "reserved", "Reserved"
        CLEANING = "cleaning", "Cleaning"
        OUT_OF_SERVICE = "out_of_service", "Out of Service"

    id: models.UUIDField[uuid.UUID, uuid.UUID] = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    is_active: models.BooleanField[bool, bool] = models.BooleanField(
        default=True,
        verbose_name="Active",
        db_index=True,
    )

    code: models.CharField[str, str] = models.CharField(
        max_length=30,
        unique=True,
        verbose_name="Table code",
    )

    capacity: models.PositiveSmallIntegerField[int, int] = (
        models.PositiveSmallIntegerField(
            default=4,
            verbose_name="Capacity",
        )
    )

    status: models.CharField[str, str] = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.AVAILABLE,
        verbose_name="Status",
        db_index=True,
    )

    created_at: models.DateTimeField[Any, Any] = models.DateTimeField(
        auto_now_add=True
    )

    updated_at: models.DateTimeField[Any, Any] = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        verbose_name = "Table"
        verbose_name_plural = "Tables"
        ordering = ["code"]

    def __str__(self) -> str:
        return self.code


class TableLayout(models.Model):
    """A restaurant floor plan: a sized board onto which tables are placed."""

    id: models.UUIDField[uuid.UUID, uuid.UUID] = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    name: models.CharField[str, str] = models.CharField(
        max_length=100,
        verbose_name="Layout name",
    )

    width: models.PositiveSmallIntegerField[int, int] = (
        models.PositiveSmallIntegerField(
            default=800,
            verbose_name="Board width (px)",
        )
    )

    height: models.PositiveSmallIntegerField[int, int] = (
        models.PositiveSmallIntegerField(
            default=600,
            verbose_name="Board height (px)",
        )
    )

    is_active: models.BooleanField[bool, bool] = models.BooleanField(
        default=True,
        verbose_name="Active",
        db_index=True,
    )

    created_at: models.DateTimeField[Any, Any] = models.DateTimeField(
        auto_now_add=True
    )

    updated_at: models.DateTimeField[Any, Any] = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        verbose_name = "Table layout"
        verbose_name_plural = "Table layouts"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class TableLayoutItem(models.Model):
    """The position of a single table within a TableLayout."""

    class Shape(models.TextChoices):
        SQUARE = "square", "Square"
        ROUND = "round", "Round"

    id: models.UUIDField[uuid.UUID, uuid.UUID] = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    layout: models.ForeignKey[TableLayout, TableLayout] = models.ForeignKey(
        TableLayout,
        on_delete=models.CASCADE,
        related_name="items",
    )

    table: models.ForeignKey[Table, Table] = models.ForeignKey(
        Table,
        on_delete=models.CASCADE,
        related_name="layout_items",
    )

    pos_x: models.PositiveSmallIntegerField[int, int] = (
        models.PositiveSmallIntegerField(
            default=0,
            verbose_name="X position (px)",
        )
    )

    pos_y: models.PositiveSmallIntegerField[int, int] = (
        models.PositiveSmallIntegerField(
            default=0,
            verbose_name="Y position (px)",
        )
    )

    shape: models.CharField[str, str] = models.CharField(
        max_length=10,
        choices=Shape.choices,
        default=Shape.SQUARE,
        verbose_name="Shape",
    )

    rotation: models.PositiveSmallIntegerField[int, int] = (
        models.PositiveSmallIntegerField(
            default=0,
            verbose_name="Rotation (deg)",
        )
    )

    class Meta:
        verbose_name = "Table layout item"
        verbose_name_plural = "Table layout items"
        constraints = [
            models.UniqueConstraint(
                fields=["layout", "table"], name="unique_table_per_layout"
            )
        ]

    def __str__(self) -> str:
        return f"{self.table.code} @ {self.layout.name}"
