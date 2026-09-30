from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.db import models

if TYPE_CHECKING:
    from gourmet.apps.menu.models import Product
    from gourmet.apps.tables.models import Table


class Order(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"
        CANCELLED = "cancelled", "Cancelled"

    class Source(models.TextChoices):
        POS = "pos", "POS (Mesero)"
        QR = "qr", "Autogestión (QR Cliente)"

    id: models.UUIDField[uuid.UUID, uuid.UUID] = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    table: models.ForeignKey[Table | None, Table | None] = models.ForeignKey(
        "tables.Table",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )
    customer_name: models.CharField[str, str] = models.CharField(
        max_length=100, blank=True, default=""
    )
    status: models.CharField[str, str] = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.OPEN,
        db_index=True,
    )
    source: models.CharField[str, str] = models.CharField(
        max_length=16,
        choices=Source.choices,
        default=Source.POS,
        db_index=True,
        verbose_name="Order source",
    )
    subtotal: models.DecimalField[Decimal, Decimal] = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    total: models.DecimalField[Decimal, Decimal] = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    discount_amount: models.DecimalField[Decimal, Decimal] = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    notes: models.TextField[str, str] = models.TextField(blank=True, default="")
    created_at: models.DateTimeField[Any, Any] = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField[Any, Any] = models.DateTimeField(auto_now=True)
    closed_at: models.DateTimeField[Any, Any] = models.DateTimeField(
        null=True, blank=True
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Order {self.pk} ({self.status})"


class OrderItem(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PREPARING = "preparing", "Preparing"
        READY = "ready", "Ready"
        SERVED = "served", "Served"
        CANCELLED = "cancelled", "Cancelled"

    id: models.UUIDField[uuid.UUID, uuid.UUID] = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    order: models.ForeignKey[Order, Order] = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="items"
    )
    product: models.ForeignKey[Product | None, Product | None] = models.ForeignKey(
        "menu.Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    product_name: models.CharField[str, str] = models.CharField(max_length=255)
    product_price: models.DecimalField[Decimal, Decimal] = models.DecimalField(
        max_digits=10, decimal_places=2
    )
    tax_rate: models.DecimalField[Decimal, Decimal] = models.DecimalField(
        max_digits=5, decimal_places=4, default=Decimal("0.0000")
    )
    discount_percent: models.DecimalField[Decimal, Decimal] = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00")
    )
    quantity: models.PositiveSmallIntegerField[int, int] = (
        models.PositiveSmallIntegerField(default=1)
    )
    notes: models.TextField[str, str] = models.TextField(blank=True, default="")
    status: models.CharField[str, str] = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    priority: models.SmallIntegerField[int, int] = models.SmallIntegerField(default=0)
    started_at: models.DateTimeField[Any, Any] = models.DateTimeField(
        null=True, blank=True
    )
    created_at: models.DateTimeField[Any, Any] = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField[Any, Any] = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["priority", "created_at"]

    def __str__(self) -> str:
        return f"{self.product_name} x{self.quantity}"


class Payment(models.Model):
    class Method(models.TextChoices):
        CASH = "cash", "Cash"
        CARD = "card", "Card"
        TRANSFER = "transfer", "Transfer"
        OTHER = "other", "Other"

    id: models.UUIDField[uuid.UUID, uuid.UUID] = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    order: models.ForeignKey[Order, Order] = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="payments"
    )
    amount: models.DecimalField[Decimal, Decimal] = models.DecimalField(
        max_digits=12, decimal_places=2
    )
    tip: models.DecimalField[Decimal, Decimal] = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    method: models.CharField[str, str] = models.CharField(
        max_length=16, choices=Method.choices
    )
    reference: models.CharField[str, str] = models.CharField(max_length=100, blank=True)
    created_at: models.DateTimeField[Any, Any] = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.method} {self.amount}"


class Invoice(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"

    id: models.UUIDField[uuid.UUID, uuid.UUID] = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    order: models.ForeignKey[Order, Order] = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="invoices"
    )
    cufe: models.CharField[str, str] = models.CharField(
        max_length=96, unique=True, blank=True, default=""
    )
    xml: models.TextField[str, str] = models.TextField(blank=True, default="")
    status: models.CharField[str, str] = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )
    dian_response: models.TextField[str, str] = models.TextField(blank=True, default="")
    created_at: models.DateTimeField[Any, Any] = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField[Any, Any] = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Invoice {self.pk} ({self.status})"


class BillSplit(models.Model):
    class Method(models.TextChoices):
        BY_ITEMS = "by_items", "By Items"
        BY_PERCENTAGE = "by_percentage", "By Percentage"
        EQUAL = "equal", "Equal"

    id: models.UUIDField[uuid.UUID, uuid.UUID] = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    order: models.ForeignKey[Order, Order] = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="splits"
    )
    label: models.CharField[str, str] = models.CharField(max_length=100)
    method: models.CharField[str, str] = models.CharField(
        max_length=16, choices=Method.choices, default=Method.BY_ITEMS
    )
    percentage: models.DecimalField[Decimal, Decimal] = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00")
    )
    amount: models.DecimalField[Decimal, Decimal] = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    paid: models.BooleanField[bool, bool] = models.BooleanField(default=False)
    created_at: models.DateTimeField[Any, Any] = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"Split {self.label} ({self.amount})"


class BillSplitItem(models.Model):
    id: models.UUIDField[uuid.UUID, uuid.UUID] = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    split: models.ForeignKey[BillSplit, BillSplit] = models.ForeignKey(
        BillSplit, on_delete=models.CASCADE, related_name="items"
    )
    order_item: models.ForeignKey[OrderItem, OrderItem] = models.ForeignKey(
        OrderItem, on_delete=models.CASCADE
    )
    quantity: models.PositiveSmallIntegerField[int, int] = (
        models.PositiveSmallIntegerField(default=1)
    )

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"SplitItem {self.order_item} x{self.quantity}"


class DailyClose(models.Model):
    closed_at: models.DateTimeField[Any, Any] = models.DateTimeField(auto_now_add=True)
    closed_by: models.ForeignKey[Any, Any] = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    total_sales: models.DecimalField[Decimal, Decimal] = models.DecimalField(
        max_digits=14, decimal_places=2
    )
    total_cash: models.DecimalField[Decimal, Decimal] = models.DecimalField(
        max_digits=14, decimal_places=2
    )
    cash_opening: models.DecimalField[Decimal, Decimal] = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    cash_counted: models.DecimalField[Decimal | None, Decimal | None] = (
        models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    )

    class Meta:
        ordering = ["-closed_at"]

    def __str__(self) -> str:
        return f"Close {self.closed_at:%Y-%m-%d %H:%M}"

    @property
    def diff(self) -> Decimal:
        return (self.cash_counted or Decimal("0")) - self.cash_opening - self.total_cash
