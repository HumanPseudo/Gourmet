from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from uuid import UUID

from django.conf import settings
from django.db import models, transaction
from django.db.models import Prefetch, QuerySet
from django.shortcuts import get_object_or_404
from django.utils import timezone

from gourmet.apps.inventory.models import InventoryMovement, ProductRecipe
from gourmet.apps.menu.models import Product
from gourmet.apps.menu.services import MenuOptionService
from gourmet.apps.tables.models import Table

from .models import BillSplit, BillSplitItem, Invoice, Order, OrderItem, Payment

logger = logging.getLogger(__name__)

TAX_RATES: dict[str, Decimal] = {
    "INC_8": Decimal("0.08"),
    "IVA_19": Decimal("0.19"),
    "IVA_5": Decimal("0.05"),
    "EXENTO": Decimal("0.00"),
}

KITCHEN_ACTORS = {"kitchen", "admin"}
WAITER_ACTORS = {"waiter", "admin"}
BOTH_ACTORS = {"kitchen", "waiter", "admin"}

# (estado_actual, estado_destino) -> (roles permitidos, efecto inventario)
TRANSITIONS: dict[tuple[str, str], tuple[set[str], str | None]] = {
    ("pending", "preparing"): (KITCHEN_ACTORS, "deduct"),
    ("preparing", "ready"): (KITCHEN_ACTORS, None),
    ("preparing", "pending"): (BOTH_ACTORS, "reverse"),
    ("ready", "preparing"): (BOTH_ACTORS, None),
    ("ready", "served"): (WAITER_ACTORS, None),
    ("ready", "cancelled"): (WAITER_ACTORS, "waste"),
    ("preparing", "cancelled"): (WAITER_ACTORS, "reverse"),
    ("pending", "served"): (WAITER_ACTORS, "deduct"),
    ("served", "ready"): (WAITER_ACTORS, None),
    ("served", "pending"): (WAITER_ACTORS, "reverse"),
    ("served", "cancelled"): (WAITER_ACTORS, "reverse"),
}

PREP_ONLY = {
    ("pending", "preparing"),
    ("preparing", "ready"),
    ("preparing", "pending"),
    ("ready", "preparing"),
    ("ready", "served"),
    ("ready", "cancelled"),
    ("preparing", "cancelled"),
    ("served", "ready"),
}

NO_PREP_ONLY = {
    ("pending", "served"),
    ("served", "pending"),
    ("served", "cancelled"),
}


class OrderService:
    STATE_RANK: dict[str, int] = {
        OrderItem.Status.PENDING: 0,
        OrderItem.Status.PREPARING: 1,
        OrderItem.Status.READY: 2,
        OrderItem.Status.SERVED: 3,
    }

    # ── Consultas base ─────────────────────────────────────────
    @staticmethod
    def _order_queryset() -> QuerySet[Order]:
        return Order.objects.prefetch_related(
            Prefetch("items", queryset=OrderItem.objects.all()),
            Prefetch("payments", queryset=Payment.objects.all()),
        ).select_related("table")

    @staticmethod
    def list_orders(status: str | None = None) -> QuerySet[Order]:
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

    # ── Creación ───────────────────────────────────────────────
    @staticmethod
    @transaction.atomic
    def create(
        table_id: UUID | None = None,
        notes: str = "",
        customer_name: str = "",
        discount_amount: Decimal = Decimal("0.00"),
        source: str = Order.Source.POS,
    ) -> Order:
        if table_id:
            Table.objects.filter(pk=table_id, is_active=True).update(
                status=Table.Status.OCCUPIED
            )
        return Order.objects.create(
            table_id=table_id,
            customer_name=customer_name,
            notes=notes,
            discount_amount=discount_amount,
            source=source,
        )

    @staticmethod
    @transaction.atomic
    def create_from_items(
        table_id: UUID,
        items: list[tuple[UUID, int]],
        notes: str = "",
        source: str = Order.Source.POS,
    ) -> Order:
        order = Order.objects.filter(
            table_id=table_id,
            status=Order.Status.OPEN,
            source=source,
        ).first()
        if order is None:
            order = OrderService.create(table_id=table_id, notes=notes, source=source)
        for product_id, quantity in items:
            OrderService.add_item(order.pk, product_id, quantity, "")
        return OrderService.checkout(order.pk)

    @staticmethod
    @transaction.atomic
    def create_from_cart_lines(
        table_id: UUID,
        lines: list[dict],
        notes: str = "",
        source: str = Order.Source.QR,
        force_new: bool = False,
    ) -> Order:
        order = None
        if not force_new:
            order = Order.objects.filter(
                table_id=table_id,
                status=Order.Status.OPEN,
                source=source,
            ).first()
        if order is None:
            order = OrderService.create(
                table_id=table_id,
                notes=notes,
                source=source,
            )
        for line in lines:
            raw_product_id = line.get("product_id")
            quantity = min(int(line.get("quantity", 1)), 99)
            option_value_ids = line.get("option_value_ids", [])
            try:
                product_id = UUID(str(raw_product_id))
            except (TypeError, ValueError) as exc:
                raise ValueError("Producto inválido en el carrito") from exc
            product = Product.objects.filter(pk=product_id).first()
            if product is None:
                raise ValueError("Producto no encontrado")
            selected_options, price_delta = MenuOptionService.validate_selection(
                product,
                option_value_ids,
            )
            unit_price = (product.price + price_delta).quantize(Decimal("0.01"))
            OrderService.add_item(
                order.pk,
                product.pk,
                quantity,
                "",
                None,
                unit_price,
                selected_options,
            )
        return OrderService.checkout(order.pk)

    # ── Items ──────────────────────────────────────────────────
    @staticmethod
    @transaction.atomic
    def add_item(
        order_id: UUID,
        product_id: UUID,
        quantity: int,
        notes: str,
        discount_percent: Decimal | None = None,
        unit_price: Decimal | None = None,
        selected_options: list | None = None,
    ) -> OrderItem:
        order = get_object_or_404(Order, pk=order_id, status=Order.Status.OPEN)
        product = get_object_or_404(Product, pk=product_id)
        tax_rate = TAX_RATES.get(product.tax_type, Decimal("0.00"))
        final_price = (
            unit_price if unit_price is not None else product.price
        ).quantize(Decimal("0.01"))
        return OrderItem.objects.create(
            order=order,
            product=product,
            product_name=product.name,
            product_price=final_price,
            quantity=quantity,
            tax_rate=tax_rate,
            discount_percent=discount_percent or Decimal("0.00"),
            notes=notes,
            selected_options=selected_options or [],
        )

    @staticmethod
    def update_item(
        order_id: UUID,
        item_id: UUID,
        quantity: int | None,
        notes: str | None,
        status: str | None,
    ) -> OrderItem:
        item = get_object_or_404(
            OrderItem,
            pk=item_id,
            order_id=order_id,
            order__status=Order.Status.OPEN,
        )
        if (
            quantity is not None
            and quantity != item.quantity
            and item.status != OrderItem.Status.PENDING
        ):
            raise ValueError("Solo se puede cambiar la cantidad de un item pendiente")
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
    def modify_item(
        order_id: UUID,
        item_id: UUID,
        quantity: int,
        option_value_ids: list,
    ) -> OrderItem:
        """Reemplaza cantidad y opciones de un item PENDING y repricia."""
        item = get_object_or_404(
            OrderItem,
            pk=item_id,
            order_id=order_id,
            order__status=Order.Status.OPEN,
            status=OrderItem.Status.PENDING,
        )
        if item.product is None:
            raise ValueError("El item no tiene producto asociado")
        selected_options, delta = MenuOptionService.validate_selection(
            item.product,
            option_value_ids,
        )
        unit_price = (item.product.price + delta).quantize(Decimal("0.01"))
        item.quantity = quantity
        item.selected_options = selected_options
        item.product_price = unit_price
        item.save(update_fields=["quantity", "selected_options", "product_price"])
        OrderService.checkout(order_id)
        return item

    @staticmethod
    @transaction.atomic
    def remove_item(order_id: UUID, item_id: UUID) -> None:
        """Cancelación de mesero: cualquier estado excepto prep served."""
        item = get_object_or_404(OrderItem, pk=item_id, order_id=order_id)
        if item.status == OrderItem.Status.PENDING:
            item.delete()
            return
        requires_prep = bool(item.product and item.product.requires_preparation)
        if item.status == OrderItem.Status.SERVED and requires_prep:
            raise ValueError("Un item servido no puede cancelarse")
        if item.status != OrderItem.Status.READY and item.product_id:
            OrderService._reverse_inventory(item.product_id, item.quantity)
        item.status = OrderItem.Status.CANCELLED
        item.save(update_fields=["status"])

    @staticmethod
    @transaction.atomic
    def set_item_status(
        order_id: UUID,
        item_id: UUID,
        status: str,
        actor: str = "kitchen",
        reason: str = "",
    ) -> OrderItem:
        """Motor de transiciones por rol con efectos de inventario."""
        item = get_object_or_404(
            OrderItem.objects.select_related("product", "order"),
            pk=item_id,
            order_id=order_id,
            order__status=Order.Status.OPEN,
        )
        key = (item.status, status)
        if key not in TRANSITIONS:
            raise ValueError(f"Transición no permitida: {item.status} → {status}")
        actors, effect = TRANSITIONS[key]
        if actor not in actors:
            raise ValueError("Tu rol no puede ejecutar esta acción")
        requires_prep = bool(item.product and item.product.requires_preparation)
        if key in PREP_ONLY and not requires_prep:
            raise ValueError("Este producto no requiere preparación")
        if key in NO_PREP_ONLY and requires_prep:
            raise ValueError("Acción solo para productos sin preparación")
        if key == ("ready", "cancelled") and not reason:
            raise ValueError("Indica el motivo de la cancelación")

        item.status = status
        if status == OrderItem.Status.PREPARING and not item.started_at:
            item.started_at = timezone.now()
        if reason:
            item.notes = f"{item.notes} | Cancelado: {reason}".strip(" |")
        item.save(update_fields=["status", "started_at", "notes"])

        if effect == "deduct" and item.product:
            OrderService._deduct_inventory(item.product, item.quantity)
        elif effect == "reverse" and item.product_id:
            OrderService._reverse_inventory(item.product_id, item.quantity)
        elif effect == "waste":
            logger.warning(
                "WASTE: item %s (%s) cancelado en ready",
                item.pk,
                item.product_name,
            )
        return item

    @staticmethod
    def set_item_priority(item_id: UUID, priority: int) -> OrderItem:
        item = get_object_or_404(OrderItem, pk=item_id)
        item.priority = priority
        item.save(update_fields=["priority"])
        return item

    # ── Totales y pagos ────────────────────────────────────────
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
        order_id: UUID,
        method: str,
        amount: Decimal,
        reference: str,
        tip: Decimal | None = None,
    ) -> Payment:
        order = get_object_or_404(Order, pk=order_id, status=Order.Status.OPEN)
        if amount <= 0:
            raise ValueError("Payment amount must be positive")
        return Payment.objects.create(
            order=order,
            method=method,
            amount=amount,
            reference=reference,
            tip=tip or Decimal("0.00"),
        )

    # ── Estado de la orden / mesa ──────────────────────────────
    @staticmethod
    def order_progress(order: Order) -> int:
        ranks = [
            OrderService.STATE_RANK.get(item.status, 0)
            for item in order.items.exclude(status=OrderItem.Status.CANCELLED)
        ]
        return max(ranks) if ranks else -1

    @staticmethod
    def can_customer_add(order: Order) -> bool:
        return order.status == Order.Status.OPEN and (
            OrderService.order_progress(order)
            <= OrderService.STATE_RANK[OrderItem.Status.PREPARING]
        )

    @staticmethod
    def can_staff_add(order: Order) -> bool:
        return order.status == Order.Status.OPEN

    @staticmethod
    def is_order_paid(order: Order) -> bool:
        total_paid = sum((p.amount for p in order.payments.all()), Decimal("0.00"))
        return total_paid >= order.total and order.total > 0

    @staticmethod
    def table_bill(table_id: UUID) -> dict:
        """Cuenta unificada: suma de todas las órdenes abiertas de la mesa."""
        orders = (
            Order.objects.filter(table_id=table_id, status=Order.Status.OPEN)
            .select_related("table")
            .prefetch_related("items", "payments")
            .order_by("created_at")
        )
        rows: list[dict] = []
        total = Decimal("0.00")
        paid = Decimal("0.00")
        for order in orders:
            order_paid = sum((p.amount for p in order.payments.all()), Decimal("0.00"))
            rows.append(
                {
                    "order": order,
                    "paid": order_paid,
                    "remaining": max(order.total - order_paid, Decimal("0.00")),
                }
            )
            total += order.total
            paid += order_paid
        return {
            "orders": rows,
            "total": total,
            "paid": paid,
            "remaining": max(total - paid, Decimal("0.00")),
        }

    # ── Cocina / entrega ───────────────────────────────────────
    @staticmethod
    def list_kitchen() -> QuerySet[OrderItem]:
        """KDS: solo items prep en pending/preparing/ready."""
        return (
            OrderItem.objects.filter(
                status__in=(
                    OrderItem.Status.PENDING,
                    OrderItem.Status.PREPARING,
                    OrderItem.Status.READY,
                )
            )
            .exclude(product__requires_preparation=False)
            .select_related("order", "order__table", "product")
            .order_by("priority", "created_at")
        )

    @staticmethod
    def list_kitchen_ready() -> QuerySet[OrderItem]:
        """Items READY de cocina (lista separada por si se requiere)."""
        return (
            OrderItem.objects.filter(status=OrderItem.Status.READY)
            .exclude(product__requires_preparation=False)
            .select_related("order", "order__table", "product")
            .order_by("updated_at")
        )

    @staticmethod
    def list_to_serve() -> QuerySet[OrderItem]:
        """Mesero: ready prep + pending no-prep de órdenes abiertas."""
        return (
            OrderItem.objects.filter(order__status=Order.Status.OPEN)
            .filter(
                models.Q(
                    status=OrderItem.Status.READY,
                    product__requires_preparation=True,
                )
                | models.Q(
                    status=OrderItem.Status.PENDING,
                    product__requires_preparation=False,
                )
            )
            .select_related("order", "order__table", "product")
            .order_by("order__table__code", "created_at")
        )

    # ── Cierre / liberación de mesa ────────────────────────────
    @staticmethod
    def _release_table_if_free(table_id: UUID | None) -> None:
        if not table_id:
            return
        still_open = Order.objects.filter(
            table_id=table_id, status=Order.Status.OPEN
        ).exists()
        if not still_open:
            Table.objects.filter(pk=table_id).update(status=Table.Status.AVAILABLE)

    @staticmethod
    @transaction.atomic
    def close(order_id: UUID, force: bool = False) -> Order:
        order = get_object_or_404(Order, pk=order_id, status=Order.Status.OPEN)
        if not force:
            active = (
                OrderItem.objects.filter(order=order)
                .exclude(
                    status__in=(
                        OrderItem.Status.SERVED,
                        OrderItem.Status.CANCELLED,
                    )
                )
                .exists()
            )
            if active:
                raise ValueError("No se puede cerrar: hay items sin servir o cancelar")
        order.status = Order.Status.CLOSED
        order.closed_at = timezone.now()
        order.save(update_fields=["status", "closed_at"])
        OrderService._release_table_if_free(order.table_id)
        OrderService._create_invoice(order)
        return OrderService.get(order.pk)

    @staticmethod
    @transaction.atomic
    def cancel(order_id: UUID) -> Order:
        order = get_object_or_404(Order, pk=order_id, status=Order.Status.OPEN)
        order.status = Order.Status.CANCELLED
        order.closed_at = timezone.now()
        order.save(update_fields=["status", "closed_at"])
        items = OrderItem.objects.filter(
            order=order,
            status=OrderItem.Status.PENDING,
        )
        for item in items:
            if item.product_id:
                OrderService._reverse_inventory(item.product_id, item.quantity)
        items.update(status=OrderItem.Status.CANCELLED)
        OrderService._release_table_if_free(order.table_id)
        return OrderService.get(order.pk)

    @staticmethod
    @transaction.atomic
    def set_table(order_id: UUID, table_id: UUID | None) -> Order:
        """Reasignación explícita. Una mesa puede tener varias órdenes."""
        order = get_object_or_404(Order, pk=order_id, status=Order.Status.OPEN)
        if order.table_id == table_id:
            return order
        previous_table_id = order.table_id
        order.table_id = table_id
        order.save(update_fields=["table_id"])
        if table_id:
            Table.objects.filter(pk=table_id, is_active=True).update(
                status=Table.Status.OCCUPIED
            )
        OrderService._release_table_if_free(previous_table_id)
        return OrderService.get(order.pk)

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
    @transaction.atomic
    def auto_close_due_tables() -> int:
        """Cierra órdenes pagadas y totalmente servidas tras N minutos."""
        minutes = getattr(settings, "AUTO_CLOSE_MINUTES", 30)
        cutoff = timezone.now() - timedelta(minutes=minutes)
        closed = 0
        orders = Order.objects.filter(status=Order.Status.OPEN).prefetch_related(
            "items", "payments"
        )
        for order in orders:
            if not OrderService.is_order_paid(order):
                continue
            active = order.items.exclude(
                status__in=(
                    OrderItem.Status.SERVED,
                    OrderItem.Status.CANCELLED,
                )
            ).exists()
            if active:
                continue
            last_activity = order.updated_at
            for item in order.items.all():
                if item.updated_at > last_activity:
                    last_activity = item.updated_at
            for payment in order.payments.all():
                if payment.created_at > last_activity:
                    last_activity = payment.created_at
            if last_activity <= cutoff:
                OrderService.close(order.pk, force=True)
                closed += 1
        return closed

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

    # ── Inventario ─────────────────────────────────────────────
    @staticmethod
    def _deduct_inventory(product: Product, quantity: int) -> None:
        recipes = ProductRecipe.objects.filter(product=product).select_related("item")
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
                    item.name,
                    item.stock,
                    needed,
                )

    @staticmethod
    def _reverse_inventory(product_id: UUID, quantity: int) -> None:
        recipes = ProductRecipe.objects.filter(product_id=product_id).select_related(
            "item"
        )
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

    # ── División de cuentas ────────────────────────────────────
    @staticmethod
    @transaction.atomic
    def split_by_items(order_id: UUID, splits_data: list[dict]) -> list[BillSplit]:
        order = get_object_or_404(Order, pk=order_id)
        items_qs = OrderItem.objects.filter(order=order).exclude(
            status=OrderItem.Status.CANCELLED,
        )
        items_by_id: dict[UUID, OrderItem] = {i.pk: i for i in items_qs}
        normalized: list[tuple[str, list[tuple[UUID, int]]]] = []
        for split_data in splits_data:
            items: list[tuple[UUID, int]] = []
            for item_data in split_data["items"]:
                oi_id = item_data["order_item_id"]
                if not isinstance(oi_id, UUID):
                    try:
                        oi_id = UUID(str(oi_id))
                    except (TypeError, ValueError) as e:
                        raise ValueError(f"Invalid order item id: {oi_id}") from e
                if oi_id not in items_by_id:
                    raise ValueError(f"Order item {oi_id} not found in order")
                items.append((oi_id, item_data["quantity"]))
            normalized.append((split_data["label"], items))
        allocated: dict[UUID, int] = defaultdict(int)
        for _, items in normalized:
            for oi_id, quantity in items:
                allocated[oi_id] += quantity
        for oi_id, total_qty in allocated.items():
            order_item = items_by_id[oi_id]
            if total_qty > order_item.quantity:
                raise ValueError(
                    f"Total split quantity {total_qty} for "
                    f"item '{order_item.product_name}' exceeds "
                    f"order quantity {order_item.quantity}"
                )
        splits: list[BillSplit] = []
        for label, items in normalized:
            split = BillSplit.objects.create(
                order=order,
                label=label,
                method=BillSplit.Method.BY_ITEMS,
            )
            amount = Decimal("0.00")
            for oi_id, quantity in items:
                order_item = items_by_id[oi_id]
                BillSplitItem.objects.create(
                    split=split,
                    order_item=order_item,
                    quantity=quantity,
                )
                line_total = order_item.product_price * quantity
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
        order = get_object_or_404(Order, pk=order_id)
        total_pct = sum(Decimal(str(d["percentage"])) for d in percentages_data)
        if total_pct != Decimal("100.00"):
            raise ValueError("Percentages must sum to 100")
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
        order = get_object_or_404(Order, pk=order_id)
        if n_splits < 2:
            raise ValueError("Must have at least 2 splits")
        if len(labels) != n_splits:
            raise ValueError("Number of labels must match splits")
        base_amount = (order.total / Decimal(n_splits)).quantize(Decimal("0.01"))
        splits: list[BillSplit] = []
        remaining = order.total
        for index, label in enumerate(labels):
            amount = remaining if index == n_splits - 1 else base_amount
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
        return BillSplit.objects.filter(order_id=order_id).prefetch_related("items")

    @staticmethod
    @transaction.atomic
    def mark_split_paid(
        split_id: UUID,
        method: str,
        reference: str = "",
        tip: Decimal | None = None,
    ) -> BillSplit:
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
        split = get_object_or_404(BillSplit, pk=split_id)
        if split.paid:
            raise ValueError("Cannot delete a paid split")
        split.delete()
