from __future__ import annotations

import uuid
from typing import Any

from django.db import models

from gourmet.apps.tables.models import Table


class Reservation(models.Model):
    class Status(models.TextChoices):
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED = "cancelled", "Cancelled"

    id: models.UUIDField[uuid.UUID, uuid.UUID] = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    table: models.ForeignKey[Table | None, Table | None] = models.ForeignKey(
        Table,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservations",
    )

    customer_name: models.CharField[str, str] = models.CharField(
        max_length=150,
        verbose_name="Customer name",
    )

    customer_phone: models.CharField[str, str] = models.CharField(
        max_length=30,
        blank=True,
        default="",
        verbose_name="Customer phone",
    )

    party_size: models.PositiveSmallIntegerField[int, int] = (
        models.PositiveSmallIntegerField(
            default=2,
            verbose_name="Party size",
        )
    )

    reserved_for: models.DateTimeField[Any, Any] = models.DateTimeField(
        db_index=True,
        verbose_name="Reserved for",
    )

    status: models.CharField[str, str] = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.CONFIRMED,
        db_index=True,
    )

    notes: models.TextField[str, str] = models.TextField(blank=True, default="")

    created_at: models.DateTimeField[Any, Any] = models.DateTimeField(
        auto_now_add=True
    )

    updated_at: models.DateTimeField[Any, Any] = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Reservation"
        verbose_name_plural = "Reservations"
        ordering = ["reserved_for"]

    def __str__(self) -> str:
        return f"{self.customer_name} @ {self.reserved_for:%Y-%m-%d %H:%M}"
