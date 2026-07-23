from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from decimal import Decimal
from uuid import UUID

from django.db import transaction
from django.db.models import Prefetch, QuerySet
from django.shortcuts import get_object_or_404
from django.utils import timezone

from gourmet.apps.inventory.models import InventoryMovement, ProductRecipe
from gourmet.apps.menu.models import Product
from gourmet.apps.tables.models import Table

from .models import BillSplit, BillSplitItem, Invoice, Order, OrderItem, Payment

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
    def create(
        table_id: UUID | None, notes: str,
        customer_name: str = "", discount_amount: Decimal | None = None,
    ) -> Order:
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
            if item.product_id:
                OrderService._reverse_inventory(item.product_id, item.quantity)
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
        items = OrderItem.objects.filter(
            order=order, status=OrderItem.Status.PENDING,
        )
        for item in items:
            if item.product_id:
                OrderService._reverse_inventory(item.product_id, item.quantity)
        items.update(status=OrderItem.Status.CANCELLED)
        if order.table_id:
            Table.objects.filter(pk=order.table_id).update(status=Table.Status.AVAILABLE)
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
    @staticmethod
    @transaction.atomic
    def set_item_status(order_id: UUID, item_id: UUID, status: str) -> OrderItem:
        item = get_object_or_404(
            OrderItem, pk=item_id, order_id=order_id,
            status__in=(
                OrderItem.Status.PENDING,
                OrderItem.Status.PREPARING,
                OrderItem.Status.READY,
            ),
        )
        was_pending = item.status == OrderItem.Status.PENDING
        item.status = status
        if status == OrderItem.Status.PREPARING and not item.started_at:
            item.started_at = timezone.now()
        item.save(update_fields=["status", "started_at"])
        if was_pending and status == OrderItem.Status.PREPARING:
            if item.product_id and item.product:
                OrderService._deduct_inventory(item.product, item.quantity)
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
                    reference="cocina:preparado",
                )
            else:
                logger.warning(
                    "Insufficient stock for %s: have %s, need %s",
                    item.name, item.stock, needed,
                )

    @staticmethod
    def _reverse_inventory(product_id: UUID, quantity: int) -> None:
        recipes = ProductRecipe.objects.filter(
            product_id=product_id,
        ).select_related("item")
        for recipe in recipes:
            qty = recipe.quantity * quantity
            item = recipe.item
            item.stock += qty
            item.save(update_fields=["stock"])
            InventoryMovement.objects.create(
                item=item,
                type=InventoryMovement.Type.IN,
                quantity=qty,
                reference="order:reverse",
            )

    # ── Bill Splitting ─────────────────────────────────────────────

    @staticmethod
    def _parse_uuid(value: UUID | str) -> UUID:
        """Parse a UUID from a string or pass through if already UUID."""
        return UUID(value) if isinstance(value, str) else value

    @staticmethod
    @transaction.atomic
    def split_by_items(order_id: UUID, splits_data: list[dict]) -> list[BillSplit]:
        """Create splits with specific items/quantities per person."""
        order = get_object_or_404(Order, pk=order_id)
        items_qs = OrderItem.objects.filter(order=order).exclude(
            status=OrderItem.Status.CANCELLED,
        )
        items_by_id: dict[UUID, OrderItem] = {i.pk: i for i in items_qs}

        # Validate all order_item_ids belong to this order
        for split_data in splits_data:
            for item_data in split_data["items"]:
                oi_id = OrderService._parse_uuid(item_data["order_item_id"])
                if oi_id not in items_by_id:
                    raise ValueError(f"Order item {oi_id} not found in order")

        # Accumulate quantities across splits per order item
        allocated: dict[UUID, int] = defaultdict(int)
        for split_data in splits_data:
            for item_data in split_data["items"]:
                oi_id = OrderService._parse_uuid(item_data["order_item_id"])
                allocated[oi_id] += item_data["quantity"]

        # Validate total quantities don't exceed order item quantities
        for oi_id, total_qty in allocated.items():
            order_item = items_by_id[oi_id]
            if total_qty > order_item.quantity:
                raise ValueError(
                    f"Total split quantity {total_qty} for "
                    f"item '{order_item.product_name}' exceeds "
                    f"order quantity {order_item.quantity}"
                )

        splits: list[BillSplit] = []
        for split_data in splits_data:
            split = BillSplit.objects.create(
                order=order,
                label=split_data["label"],
                method=BillSplit.Method.BY_ITEMS,
            )
            amount = Decimal("0.00")
            for item_data in split_data["items"]:
                oi_id = OrderService._parse_uuid(item_data["order_item_id"])
                order_item = items_by_id[oi_id]
                BillSplitItem.objects.create(
                    split=split,
                    order_item=order_item,
                    quantity=item_data["quantity"],
                )
                line_total = order_item.product_price * item_data["quantity"]
                disc_pct = order_item.discount_percent / Decimal("100")
                discount_amt = line_total * disc_pct
                line_after = line_total - discount_amt
                amount += line_after * (Decimal("1") + order_item.tax_rate)
            split.amount = amount.quantize(Decimal("0.01"))
            split.save(update_fields=["amount"])
            splits.append(split)
        return splits

    @staticmethod
    @transaction.atomic
    def split_by_percentage(
        order_id: UUID, percentages_data: list[dict]
    ) -> list[BillSplit]:
        """Split order total by percentage."""
        order = get_object_or_404(Order, pk=order_id)
        total_pct = sum(Decimal(str(d["percentage"])) for d in percentages_data)
        if total_pct != Decimal("100.00"):
            raise ValueError(
                f"Percentages must sum to 100, got {total_pct}"
            )
        splits: list[BillSplit] = []
        for data in percentages_data:
            pct = Decimal(str(data["percentage"]))
            amount = (order.total * pct / Decimal("100")).quantize(Decimal("0.01"))
            split = BillSplit.objects.create(
                order=order,
                label=data["label"],
                method=BillSplit.Method.BY_PERCENTAGE,
                percentage=pct,
                amount=amount,
            )
            splits.append(split)
        return splits

    @staticmethod
    @transaction.atomic
    def split_equal(
        order_id: UUID, n_splits: int, labels: list[str]
    ) -> list[BillSplit]:
        """Split order total equally into N parts."""
        order = get_object_or_404(Order, pk=order_id)
        if n_splits < 2:
            raise ValueError("Must have at least 2 splits")
        if len(labels) != n_splits:
            raise ValueError("Number of labels must match number of splits")
        base_amount = (order.total / Decimal(n_splits)).quantize(Decimal("0.01"))
        splits: list[BillSplit] = []
        remaining = order.total
        for i, label in enumerate(labels):
            if i == n_splits - 1:
                amount = remaining
            else:
                amount = base_amount
            remaining -= amount
            split = BillSplit.objects.create(
                order=order,
                label=label,
                method=BillSplit.Method.EQUAL,
                amount=amount,
            )
            splits.append(split)
        return splits

    @staticmethod
    def get_splits(order_id: UUID) -> QuerySet[BillSplit]:
        """List all splits for an order."""
        return BillSplit.objects.filter(order_id=order_id).prefetch_related("items")

    @staticmethod
    @transaction.atomic
    def mark_split_paid(
        split_id: UUID, method: str, reference: str = "", tip: Decimal | None = None,
    ) -> BillSplit:
        """Mark a split as paid and create a Payment on the order."""
        split = get_object_or_404(BillSplit, pk=split_id)
        if split.paid:
            raise ValueError("Split is already paid")
        split.paid = True
        split.save(update_fields=["paid"])
        Payment.objects.create(
            order=split.order,
            amount=split.amount,
            method=method,
            reference=reference,
            tip=tip or Decimal("0.00"),
        )
        return split

    @staticmethod
    @transaction.atomic
    def delete_split(split_id: UUID) -> None:
        """Remove a split."""
        split = get_object_or_404(BillSplit, pk=split_id)
        if split.paid:
            raise ValueError("Cannot delete a paid split")
        split.delete()
