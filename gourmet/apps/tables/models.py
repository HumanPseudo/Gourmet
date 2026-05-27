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
