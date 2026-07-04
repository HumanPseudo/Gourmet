from __future__ import annotations

import hashlib
import logging
from decimal import Decimal
from uuid import UUID

from django.db import transaction
from django.db.models import Prefetch, QuerySet, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone

from gourmet.apps.inventory.models import InventoryMovement, ProductRecipe
from gourmet.apps.menu.models import Product
from gourmet.apps.tables.models import Table

from .models import Invoice, Order, OrderItem, Payment

logger = logging.getLogger(__name__)


TAX_RATES: dict[str, Decimal] = {
    "INC_8": Decimal("0.08"),
    "IVA_19": Decimal("0.19"),
    "IVA_5": Decimal("0.05"),
    "EXENTO": Decimal("0.00"),
}


class OrderService:
    @staticmethod
    def _order_queryset() -> QuerySet[Order]:
        return Order.objects.prefetch_related(
            Prefetch("items", queryset=OrderItem.objects.all()),
            Prefetch("payments", queryset=Payment.objects.all()),
        ).select_related("table")

    @staticmethod
    def list(status: str | None = None) -> QuerySet[Order]:
        qs = OrderService._order_queryset()
        if status:
            qs = qs.filter(status=status)
        return qs

    @staticmethod
    def list_active() -> QuerySet[Order]:
        return OrderService._order_queryset().filter(status=Order.Status.OPEN)

    @staticmethod
    def get(order_id: UUID) -> Order:
        return get_object_or_404(OrderService._order_queryset(), pk=order_id)

    @staticmethod
    @transaction.atomic
    def create(table_id: UUID | None, notes: str, customer_name: str = "", discount_amount: Decimal | None = None) -> Order:
        if table_id:
            Table.objects.filter(pk=table_id, is_active=True).update(
                status=Table.Status.OCCUPIED
            )
        return Order.objects.create(
            table_id=table_id,
            notes=notes,
            customer_name=customer_name,
            discount_amount=discount_amount or Decimal("0.00"),
        )

    @staticmethod
    @transaction.atomic
    def add_item(
        order_id: UUID, product_id: UUID, quantity: int, notes: str,
        discount_percent: Decimal | None = None,
    ) -> OrderItem:
        order = get_object_or_404(Order, pk=order_id, status=Order.Status.OPEN)
        product = get_object_or_404(Product, pk=product_id)
        tax_rate = TAX_RATES.get(product.tax_type, Decimal("0.00"))
        item = OrderItem.objects.create(
            order=order,
            product=product,
            product_name=product.name,
            product_price=product.price,
            quantity=quantity,
            tax_rate=tax_rate,
            discount_percent=discount_percent or Decimal("0.00"),
            notes=notes,
        )
        OrderService._deduct_inventory(product, quantity)
        return item

    @staticmethod
    def update_item(
        order_id: UUID, item_id: UUID, quantity: int | None, notes: str | None,
        status: str | None,
    ) -> OrderItem:
        item = get_object_or_404(
            OrderItem, pk=item_id, order_id=order_id, order__status=Order.Status.OPEN
        )
        if quantity is not None:
            item.quantity = quantity
        if notes is not None:
            item.notes = notes
        if status is not None:
            item.status = status
        item.save()
        return item

    @staticmethod
    @transaction.atomic
    def remove_item(order_id: UUID, item_id: UUID) -> None:
        item = get_object_or_404(OrderItem, pk=item_id, order_id=order_id)
        if item.status not in (OrderItem.Status.PENDING,):
            item.status = OrderItem.Status.CANCELLED
            item.save()
        else:
            item.delete()

    @staticmethod
    @transaction.atomic
    def checkout(order_id: UUID) -> Order:
        order = get_object_or_404(Order, pk=order_id, status=Order.Status.OPEN)
        items = OrderItem.objects.filter(order=order).exclude(
            status=OrderItem.Status.CANCELLED
        )
        subtotal = Decimal("0.00")
        tax_total = Decimal("0.00")
        discount_total = Decimal("0.00")
        for item in items:
            if item.product_price is not None:
                line_total = item.product_price * item.quantity
                discount_amt = line_total * (item.discount_percent / Decimal("100"))
                discount_total += discount_amt
                line_after = line_total - discount_amt
                subtotal += line_after
                tax_total += line_after * item.tax_rate
        order.discount_amount = discount_total.quantize(Decimal("0.01"))
        order.subtotal = subtotal.quantize(Decimal("0.01"))
        order.total = (subtotal + tax_total).quantize(Decimal("0.01"))
        order.save(update_fields=["discount_amount", "subtotal", "total"])
        return OrderService.get(order.pk)

    @staticmethod
    @transaction.atomic
    def pay(
        order_id: UUID, method: str, amount: Decimal, reference: str,
        tip: Decimal | None = None,
    ) -> Payment:
        order = get_object_or_404(Order, pk=order_id, status=Order.Status.OPEN)
        if amount <= 0:
            raise ValueError("Payment amount must be positive")
        payment = Payment.objects.create(
            order=order, method=method, amount=amount, reference=reference,
            tip=tip or Decimal("0.00"),
        )
        return payment

    @staticmethod
    @transaction.atomic
    def close(order_id: UUID) -> Order:
        order = get_object_or_404(Order, pk=order_id, status=Order.Status.OPEN)
        paid = (
            Payment.objects.filter(order=order).aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )
        if paid < order.total:
            raise ValueError(
                f"Order total is {order.total} but only {paid} paid"
            )
        if order.table_id:
            Table.objects.filter(pk=order.table_id).update(status=Table.Status.AVAILABLE)
        order.status = Order.Status.CLOSED
        order.closed_at = timezone.now()
        order.save(update_fields=["status", "closed_at"])
        OrderService._create_invoice(order)
        return OrderService.get(order.pk)

    @staticmethod
    def _create_invoice(order: Order) -> None:
        items_xml = "".join(
            f"<item><name>{i.product_name}</name><qty>{i.quantity}</qty>"
            f"<price>{i.product_price}</price><tax>{i.tax_rate}</tax></item>"
            for i in order.items.exclude(status=OrderItem.Status.CANCELLED)
        )
        xml = (
            f"<invoice><id>{order.pk}</id>"
            f"<date>{order.closed_at or order.created_at}</date>"
            f"<subtotal>{order.subtotal}</subtotal><total>{order.total}</total>"
            f"{items_xml}</invoice>"
        )
        cufe = hashlib.sha256(xml.encode()).hexdigest().upper()
        Invoice.objects.create(
            order=order, xml=xml, cufe=cufe, status=Invoice.Status.PENDING
        )

    @staticmethod
    @transaction.atomic
    def cancel(order_id: UUID) -> Order:
        order = get_object_or_404(Order, pk=order_id, status=Order.Status.OPEN)
        order.status = Order.Status.CANCELLED
        order.closed_at = timezone.now()
        order.save(update_fields=["status", "closed_at"])
        OrderItem.objects.filter(order=order, status=OrderItem.Status.PENDING).update(
            status=OrderItem.Status.CANCELLED
        )
        return OrderService.get(order.pk)

    @staticmethod
    def list_kitchen() -> QuerySet[OrderItem]:
        return (
            OrderItem.objects.filter(
                status__in=(OrderItem.Status.PENDING, OrderItem.Status.PREPARING)
            )
            .select_related("order")
            .order_by("priority", "created_at")
        )

    @staticmethod
    def set_item_status(order_id: UUID, item_id: UUID, status: str) -> OrderItem:
        item = get_object_or_404(
            OrderItem, pk=item_id, order_id=order_id,
            status__in=(
                OrderItem.Status.PENDING,
                OrderItem.Status.PREPARING,
                OrderItem.Status.READY,
            ),
        )
        item.status = status
        if status == OrderItem.Status.PREPARING and not item.started_at:
            item.started_at = timezone.now()
        item.save(update_fields=["status", "started_at"])
        return item

    @staticmethod
    def set_item_priority(item_id: UUID, priority: int) -> OrderItem:
        item = get_object_or_404(OrderItem, pk=item_id)
        item.priority = priority
        item.save(update_fields=["priority"])
        return item

    @staticmethod
    @transaction.atomic
    def reopen(order_id: UUID) -> Order:
        order = get_object_or_404(Order, pk=order_id, status=Order.Status.CLOSED)
        order.status = Order.Status.OPEN
        order.closed_at = None
        order.save(update_fields=["status", "closed_at"])
        if order.table_id:
            Table.objects.filter(pk=order.table_id).update(status=Table.Status.OCCUPIED)
        return OrderService.get(order.pk)

    @staticmethod
    def _deduct_inventory(product: Product, quantity: int) -> None:
        recipes = ProductRecipe.objects.filter(
            product=product,
        ).select_related("item")
        for recipe in recipes:
            needed = recipe.quantity * quantity
            item = recipe.item
            if item.stock >= needed:
                item.stock -= needed
                item.save(update_fields=["stock"])
                InventoryMovement.objects.create(
                    item=item,
                    type=InventoryMovement.Type.OUT,
                    quantity=needed,
                    reference="order:auto",
                )
            else:
                logger.warning(
                    "Insufficient stock for %s: have %s, need %s",
                    item.name, item.stock, needed,
                )
