import csv
import hashlib
import io
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

import qrcode  # type: ignore
from django.conf import settings
from django.contrib import messages
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone as django_tz
from django.views.decorators.http import require_POST

from gourmet.apps.accounts.audit import log_audit
from gourmet.apps.accounts.auth import role_required
from gourmet.apps.accounts.models import User
from gourmet.apps.menu.models import Category, Product
from gourmet.apps.menu.services import (
    MenuAvailabilityService,
    MenuOptionService,
)
from gourmet.apps.tables.models import Table, TableLayout
from gourmet.apps.tables.services import TableService

from .models import DailyClose, Order, OrderItem
from .services import OrderService


def _order_json(order: Order) -> dict:
    total_paid = sum((p.amount for p in order.payments.all()), Decimal("0.00"))
    items = order.items.exclude(status=OrderItem.Status.CANCELLED)
    tax_total = Decimal("0.00")
    for i in items:
        tax_total += i.product_price * i.quantity * i.tax_rate
    return {
        "id": str(order.pk),
        "table_id": str(order.table_id) if order.table_id else None,
        "table_code": order.table.code if order.table else None,
        "customer_name": order.customer_name,
        "status": order.status,
        "subtotal": str(order.subtotal),
        "total": str(order.total),
        "tax_total": str(tax_total.quantize(Decimal("0.01"))),
        "total_paid": str(total_paid),
        "items": [
            {
                "id": str(i.pk),
                "name": i.product_name,
                "price": str(i.product_price),
                "quantity": i.quantity,
                "status": i.status,
                "selected_options": i.selected_options or [],
            }
            for i in items
        ],
    }


def _mins(delta: timedelta) -> int:
    return int(delta.total_seconds() / 60)


@role_required("waiter", "admin")
def pos(request):
    from gourmet.apps.inventory.models import ProductRecipe

    tables = Table.objects.filter(is_active=True).order_by("code")
    tax_choices = Product.TaxChoices.choices
    out_of_stock = set()
    low_stock = set()
    for r in ProductRecipe.objects.select_related("item").iterator():
        if r.item.stock < r.quantity:
            out_of_stock.add(str(r.product_id))
        elif r.item.stock < r.quantity * 5:
            low_stock.add(str(r.product_id))
    return render(
        request,
        "pos/pos.html",
        {
            "tables": tables,
            "tax_choices": tax_choices,
            "out_of_stock_json": list(out_of_stock),
            "low_stock_json": list(low_stock),
        },
    )


def _add_pos_item(order: Order, item: dict) -> OrderItem:
    """Agrega un item de POS validando opciones y recalculando precio en servidor."""
    product = get_object_or_404(Product, pk=item["product_id"])
    option_value_ids = item.get("option_value_ids", [])
    unit_price = None
    selected_options: list = []
    if option_value_ids:
        selected_options, delta = MenuOptionService.validate_selection(
            product, option_value_ids
        )
        unit_price = (product.price + delta).quantize(Decimal("0.01"))
    return OrderService.add_item(
        order.pk,
        product.pk,
        item.get("quantity", 1),
        item.get("notes", ""),
        Decimal(str(item.get("discount_percent", 0))),
        unit_price=unit_price,
        selected_options=selected_options,
    )


@role_required("waiter", "admin")
@require_POST
def pos_create_order(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError as e:
        return JsonResponse({"error": f"Invalid JSON: {e}"}, status=400)
    try:
        order = OrderService.create(
            table_id=data.get("table_id"),
            notes=data.get("notes", ""),
            customer_name=data.get("customer_name", ""),
            discount_amount=Decimal(str(data.get("discount_amount", 0))),
        )
        log_audit(request, "order.created", str(order.pk)[:8])
        for item in data.get("items", []):
            _add_pos_item(order, item)
        if data.get("checkout", True):
            order = OrderService.checkout(order.pk)
        return JsonResponse(_order_json(order))
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@role_required("waiter", "admin")
@require_POST
def pos_pay(request, order_id):
    data = json.loads(request.body)
    try:
        payment = OrderService.pay(
            order_id,
            data["method"],
            Decimal(str(data["amount"])),
            data.get("reference", ""),
            Decimal(str(data.get("tip", 0))),
        )
        log_audit(
            request,
            "payment.added",
            f"Order {str(order_id)[:8]}",
            f"{data['method']} ${data['amount']}",
        )
        return JsonResponse(
            {
                "id": str(payment.pk),
                "amount": str(payment.amount),
                "method": payment.method,
                "tip": str(payment.tip),
            }
        )
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)


@role_required("waiter", "admin")
@require_POST
def pos_add_items(request, order_id):
    data = json.loads(request.body)
    order = get_object_or_404(Order, pk=order_id, status=Order.Status.OPEN)
    for item in data.get("items", []):
        _add_pos_item(order, item)
    log_audit(request, "order.items_added", f"Order {str(order_id)[:8]}")
    order = OrderService.checkout(order.pk)
    return JsonResponse(_order_json(order))


@role_required("waiter", "admin")
@require_POST
def pos_close(request, order_id):
    try:
        OrderService.close(order_id)
        log_audit(request, "order.closed", f"Order {str(order_id)[:8]}")
        return JsonResponse({"status": "closed"})
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)


@role_required("waiter", "admin")
def pos_order_json(request, order_id):
    order = get_object_or_404(
        Order.objects.select_related("table").prefetch_related("items", "payments"),
        pk=order_id,
    )
    return JsonResponse(_order_json(order))


@role_required("waiter", "admin")
@require_POST
def pos_remove_item(request, order_id, item_id):
    try:
        OrderService.remove_item(order_id, item_id)
        order = OrderService.checkout(order_id)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)
    log_audit(request, "order.item_removed", f"Order {str(order_id)[:8]}")
    return JsonResponse(_order_json(order))


@role_required("waiter", "admin")
@require_POST
def pos_set_table(request, order_id):
    data = json.loads(request.body)
    try:
        order = OrderService.set_table(order_id, data.get("table_id") or None)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)
    log_audit(request, "order.table_changed", f"Order {str(order_id)[:8]}")
    return JsonResponse(_order_json(order))


@role_required("waiter", "admin")
def pos_floor_status(request):
    layout = (
        TableLayout.objects.filter(is_active=True)
        .prefetch_related("items__table")
        .first()
    )
    open_order_by_table = dict(
        Order.objects.filter(
            status=Order.Status.OPEN, table_id__isnull=False
        ).values_list("table_id", "id")
    )

    def _table_json(table, pos_x=None, pos_y=None, shape=None, rotation=None):
        order_id = open_order_by_table.get(table.id)
        return {
            "table_id": str(table.id),
            "code": table.code,
            "capacity": table.capacity,
            "status": table.status,
            "order_id": str(order_id) if order_id else None,
            "pos_x": pos_x,
            "pos_y": pos_y,
            "shape": shape,
            "rotation": rotation,
        }

    placed_ids: set = set()
    items = []
    layout_json = None
    if layout:
        layout_json = {"width": layout.width, "height": layout.height}
        for item in layout.items.all():
            placed_ids.add(item.table_id)
            items.append(
                _table_json(
                    item.table, item.pos_x, item.pos_y, item.shape, item.rotation
                )
            )

    unplaced = [
        _table_json(t)
        for t in Table.objects.filter(is_active=True)
        .exclude(pk__in=placed_ids)
        .order_by("code")
    ]

    no_table_orders = [
        {
            "order_id": str(o.pk),
            "customer_name": o.customer_name,
            "item_count": o.items.exclude(status=OrderItem.Status.CANCELLED).count(),
            "total": str(o.total),
        }
        for o in Order.objects.filter(
            status=Order.Status.OPEN, table_id__isnull=True
        ).order_by("created_at")
    ]

    return JsonResponse(
        {
            "layout": layout_json,
            "items": items,
            "unplaced": unplaced,
            "no_table_orders": no_table_orders,
        }
    )


@role_required("waiter", "admin")
def floor_view(request):
    if request.method == "POST":
        table = get_object_or_404(Table, pk=request.POST.get("table_id"))
        TableService.assign_waiter(table, request.POST.get("waiter_id") or None)
        log_audit(request, "table.waiter_assigned", table.code)
        return redirect("floor_view")

    layout = (
        TableLayout.objects.filter(is_active=True)
        .prefetch_related("items__table__assigned_waiter")
        .first()
    )
    open_order_by_table = dict(
        Order.objects.filter(
            status=Order.Status.OPEN, table_id__isnull=False
        ).values_list("table_id", "id")
    )

    def _row(table: Table, pos_x=None, pos_y=None, shape=None, rotation=None):
        return {
            "table": table,
            "pos_x": pos_x,
            "pos_y": pos_y,
            "shape": shape,
            "rotation": rotation,
            "order_id": open_order_by_table.get(table.pk),
        }

    placed_ids: set = set()
    positioned = []
    layout_size = None
    if layout:
        layout_size = {"width": layout.width, "height": layout.height}
        for item in layout.items.all():
            placed_ids.add(item.table_id)
            positioned.append(
                _row(item.table, item.pos_x, item.pos_y, item.shape, item.rotation)
            )

    unplaced = [
        _row(t)
        for t in Table.objects.filter(is_active=True)
        .exclude(pk__in=placed_ids)
        .select_related("assigned_waiter")
        .order_by("code")
    ]

    waiters = User.objects.filter(role__name="waiter", is_active=True).order_by("name")

    return render(
        request,
        "pos/floor_view.html",
        {
            "layout_size": layout_size,
            "positioned": positioned,
            "unplaced": unplaced,
            "waiters": waiters,
        },
    )


@role_required("waiter", "kitchen", "admin")
def kitchen(request):
    items = OrderService.list_kitchen()
    now = datetime.now(UTC)
    pending = preparing = ready = 0
    for i in items:
        i.elapsed = (
            int((now - i.created_at).total_seconds() / 60) if i.created_at else 0
        )
        i.preparing = (
            int((now - i.started_at).total_seconds() / 60) if i.started_at else None
        )
        i.table_code = i.order.table.code if i.order.table else ""
        if i.status == "pending":
            pending += 1
        elif i.status == "preparing":
            preparing += 1
        elif i.status == "ready":
            ready += 1
    groups: dict[str, list] = {}
    for i in items:
        table = i.table_code or "—"
        groups.setdefault(table, []).append(i)
    return render(
        request,
        "pos/kitchen.html",
        {
            "items": items,
            "groups": groups,
            "is_admin": request.user.is_superuser
            or (request.user.role and request.user.role.name == "admin"),
            "pending_count": pending,
            "preparing_count": preparing,
            "ready_count": ready,
        },
    )


@role_required("waiter", "kitchen", "admin")
def order_list(request):
    orders = (
        Order.objects.all()
        .select_related("table")
        .prefetch_related("items", "payments")
    )
    for o in orders:
        o.total_paid_ = sum(p.amount for p in o.payments.all())
        o.pending_ = o.total - o.total_paid_
    return render(request, "pos/orders.html", {"orders": orders})


@role_required("waiter", "kitchen", "admin")
def order_detail(request, order_id):
    from gourmet.apps.accounts.models import AuthToken

    order = get_object_or_404(
        Order.objects.select_related("table").prefetch_related(
            "items__product",
            "payments",
        ),
        pk=order_id,
    )
    total_paid = sum(p.amount for p in order.payments.all())
    token = AuthToken.objects.filter(
        user=request.user
    ).first() or AuthToken.create_token(request.user)
    return render(
        request,
        "pos/order_detail.html",
        {
            "order": order,
            "total_paid": total_paid,
            "pending": order.total - total_paid,
            "api_token": token.key,
        },
    )


@role_required("waiter", "admin")
def create_order(request):
    tables = Table.objects.filter(is_active=True).order_by("code")
    products = (
        Product.objects.filter(is_available=True)
        .select_related("category")
        .order_by("category__sort_order", "sort_order", "name")
    )

    if request.method == "POST":
        table_id = request.POST.get("table_id") or None
        notes = request.POST.get("notes", "")
        product_ids = request.POST.getlist("product_id")
        quantities = request.POST.getlist("quantity")

        order = OrderService.create(table_id=table_id, notes=notes)
        log_audit(request, "order.created", str(order.pk)[:8])

        for pid, qty in zip(product_ids, quantities, strict=False):
            qty = int(qty)
            if qty > 0:
                OrderService.add_item(order.pk, pid, qty, "")

        messages.success(request, f"Orden #{str(order.pk)[:8]} creada")
        return redirect("order_detail", order_id=order.pk)

    return render(
        request,
        "pos/create_order.html",
        {"tables": tables, "products": products},
    )


@role_required("waiter", "admin")
def add_payment(request, order_id):
    get_object_or_404(Order, pk=order_id, status=Order.Status.OPEN)
    if request.method == "POST":
        method = request.POST["method"]
        amount = Decimal(request.POST["amount"])
        reference = request.POST.get("reference", "")
        try:
            OrderService.pay(order_id, method, amount, reference)
            log_audit(
                request,
                "payment.added",
                f"Order {str(order_id)[:8]}",
                f"{method} ${amount}",
            )
            messages.success(request, "Pago registrado")
        except ValueError as e:
            messages.error(request, str(e))
        return redirect("order_detail", order_id=order_id)


@role_required("waiter", "admin")
def close_order(request, order_id):
    get_object_or_404(Order, pk=order_id, status=Order.Status.OPEN)
    if request.method == "POST":
        try:
            OrderService.close(order_id)
            log_audit(request, "order.closed", f"Order {str(order_id)[:8]}")
            messages.success(request, "Orden cerrada")
            return redirect("order_list")
        except ValueError as e:
            messages.error(request, str(e))
    return redirect("order_detail", order_id=order_id)


@role_required("admin")
def dashboard(request):
    today = django_tz.localdate()
    desde = request.GET.get("desde", "")
    hasta = request.GET.get("hasta", "")
    if desde and hasta:
        try:
            d = django_tz.datetime(*map(int, desde.split("-")))
            h = django_tz.datetime(*map(int, hasta.split("-")), 23, 59, 59)
            orders = Order.objects.filter(
                created_at__range=(d, h),
                status=Order.Status.CLOSED,
            ).prefetch_related("payments", "items")
        except (ValueError, IndexError):
            desde = hasta = ""
            orders = Order.objects.filter(
                created_at__date=today,
                status=Order.Status.CLOSED,
            ).prefetch_related("payments", "items")
    else:
        orders = Order.objects.filter(
            created_at__date=today,
            status=Order.Status.CLOSED,
        ).prefetch_related("payments", "items")
        desde = today.isoformat()
        hasta = today.isoformat()

    total_sales = Decimal("0.00")
    total_tax = Decimal("0.00")
    total_tips = Decimal("0.00")
    total_discount = Decimal("0.00")
    by_method: dict[str, Decimal] = {}
    item_count = 0
    top_products: dict[str, int] = {}

    for o in orders:
        total_sales += o.total
        total_discount += o.discount_amount
        for p in o.payments.all():
            total_tips += p.tip
            by_method[p.method] = by_method.get(p.method, Decimal("0.00")) + p.amount
        for i in o.items.exclude(status=OrderItem.Status.CANCELLED):
            item_count += i.quantity
            tax = i.product_price * i.quantity * i.tax_rate
            total_tax += tax
            name = i.product_name
            top_products[name] = top_products.get(name, 0) + i.quantity

    top_sorted = sorted(top_products.items(), key=lambda x: -x[1])[:10]

    return render(
        request,
        "pos/dashboard.html",
        {
            "today": today,
            "desde": desde,
            "hasta": hasta,
            "order_count": orders.count(),
            "total_sales": total_sales.quantize(Decimal("0.01")),
            "total_tax": total_tax.quantize(Decimal("0.01")),
            "total_tips": total_tips.quantize(Decimal("0.01")),
            "total_discount": total_discount.quantize(Decimal("0.01")),
            "by_method": by_method,
            "item_count": item_count,
            "top_products": top_sorted,
        },
    )


@role_required("admin")
def close_report(request):
    today = django_tz.localdate()
    orders = Order.objects.filter(
        created_at__date=today,
        status=Order.Status.CLOSED,
    ).prefetch_related("payments", "items")
    total_sales = Decimal("0.00")
    total_cash = Decimal("0.00")
    total_tax = Decimal("0.00")
    total_tips = Decimal("0.00")
    total_discount = Decimal("0.00")
    for o in orders:
        total_sales += o.total
        total_discount += o.discount_amount
        for p in o.payments.all():
            total_tips += p.tip
            if p.method == "cash":
                total_cash += p.amount
        for i in o.items.exclude(status=OrderItem.Status.CANCELLED):
            total_tax += i.product_price * i.quantity * i.tax_rate
    saved = None
    diff = None
    expected_cash = total_cash
    if request.method == "POST":
        cash_opening = Decimal(request.POST.get("cash_opening", "0"))
        cash_counted = Decimal(request.POST.get("cash_counted", "0"))
        expected_cash = cash_opening + total_cash
        diff = cash_counted - expected_cash
        saved = DailyClose.objects.create(
            closed_by=request.user if request.user.is_authenticated else None,
            total_sales=total_sales,
            total_cash=total_cash,
            cash_opening=cash_opening,
            cash_counted=cash_counted,
        )
        log_audit(
            request,
            "daily_close.saved",
            f"cash={total_cash} counted={cash_counted} diff={diff}",
        )
        saved_count = orders.count()
    else:
        saved_count = 0
    history = DailyClose.objects.all()[:20]
    return render(
        request,
        "pos/close_report.html",
        {
            "today": today,
            "order_count": orders.count(),
            "saved_count": saved_count,
            "total_sales": total_sales.quantize(Decimal("0.01")),
            "total_cash": total_cash.quantize(Decimal("0.01")),
            "total_tax": total_tax.quantize(Decimal("0.01")),
            "total_tips": total_tips.quantize(Decimal("0.01")),
            "total_discount": total_discount.quantize(Decimal("0.01")),
            "expected_cash": expected_cash,
            "diff": diff.quantize(Decimal("0.01")) if diff is not None else None,
            "saved": saved,
            "history": history,
        },
    )


@role_required("admin")
def sales_csv(request):
    desde = request.GET.get("desde", "")
    hasta = request.GET.get("hasta", "")
    today = django_tz.localdate()
    base = Order.objects.filter(
        status=Order.Status.CLOSED,
    ).prefetch_related("items", "payments")
    if desde and hasta:
        try:
            d = django_tz.datetime(*map(int, desde.split("-")))
            h = django_tz.datetime(*map(int, hasta.split("-")), 23, 59, 59)
            orders = base.filter(created_at__range=(d, h))
        except (ValueError, IndexError):
            orders = base.filter(created_at__date=today)
    else:
        orders = base.filter(created_at__date=today)
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = "attachment; filename=ventas.csv"
    w = csv.writer(response)
    w.writerow(
        [
            "Orden",
            "Fecha",
            "Mesa",
            "Subtotal",
            "Descuento",
            "Total",
            "Metodo",
            "Propina",
        ]
    )
    for o in orders:
        row = [
            str(o.pk)[:8],
            o.created_at,
            o.table.code if o.table else "",
            o.subtotal,
            o.discount_amount,
            o.total,
        ]
        for p in o.payments.all():
            w.writerow([*row, p.method, p.tip])
        if not o.payments.exists():
            w.writerow([*row, "", ""])
    return response


@role_required("admin")
@require_POST
def reopen_order(request, order_id):
    try:
        OrderService.reopen(order_id)
        log_audit(request, "order.reopened", f"Order {str(order_id)[:8]}")
        messages.success(request, "Orden reabierta")
    except ValueError as e:
        messages.error(request, str(e))
    return redirect("order_detail", order_id=order_id)


@role_required("waiter", "admin")
@require_POST
def split_order(request, order_id):
    data = json.loads(request.body)
    item_ids = data.get("item_ids", [])
    if not item_ids:
        return JsonResponse({"error": "No items selected"}, status=400)
    order = get_object_or_404(Order, pk=order_id, status=Order.Status.OPEN)
    items_to_move = OrderItem.objects.filter(
        pk__in=item_ids,
        order=order,
        status__in=(OrderItem.Status.PENDING,),
    )
    if not items_to_move.exists():
        return JsonResponse({"error": "No movable items selected"}, status=400)
    new_order = Order.objects.create(
        table=order.table,
        notes=f"Split from {str(order.pk)[:8]}",
    )
    items_to_move.update(order=new_order)
    OrderService.checkout(new_order.pk)
    new_order.refresh_from_db()
    log_audit(
        request,
        "order.splitted",
        f"Order {str(order_id)[:8]} → {str(new_order.pk)[:8]}",
    )
    return JsonResponse(
        {
            "new_order_id": str(new_order.pk),
            "moved": items_to_move.count(),
        }
    )


@role_required("waiter", "admin")
def print_receipt(request, order_id):
    order = get_object_or_404(
        Order.objects.select_related("table").prefetch_related(
            "items__product",
            "payments",
        ),
        pk=order_id,
    )
    items = order.items.exclude(status=OrderItem.Status.CANCELLED)
    tax_totals = {}
    for i in items:
        rate_pct = int(i.tax_rate * 100)
        tax = i.product_price * i.quantity * i.tax_rate
        tax_totals[rate_pct] = tax_totals.get(rate_pct, Decimal("0")) + tax
    return render(
        request,
        "pos/print_receipt.html",
        {
            "order": order,
            "tax_totals": tax_totals,
            "business_name": settings.BUSINESS_NAME,
            "business_nit": settings.BUSINESS_NIT,
        },
    )


@role_required("waiter", "kitchen", "admin")
def print_kitchen(request, order_id):
    order = get_object_or_404(
        Order.objects.select_related("table").prefetch_related(
            "items__product",
        ),
        pk=order_id,
    )
    return render(
        request,
        "pos/print_kitchen.html",
        {"order": order, "now": django_tz.now()},
    )


@role_required("admin")
@require_POST
def pos_set_priority(request, item_id):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        data = request.POST
    priority = int(data.get("priority", 0))
    OrderService.set_item_priority(item_id, priority)
    log_audit(request, "item.priority", str(item_id)[:8], f"priority={priority}")
    item = get_object_or_404(
        OrderItem.objects.select_related("order__table"),
        pk=item_id,
    )
    now = datetime.now(UTC)
    item.elapsed = _mins(now - item.created_at) if item.created_at else 0
    item.preparing = _mins(now - item.started_at) if item.started_at else None
    item.table_code = item.order.table.code if item.order.table else ""
    html = render_to_string(
        "pos/_kitchen_card.html",
        {
            "item": item,
            "is_admin": True,
        },
        request=request,
    )
    return HttpResponse(html)


@role_required("waiter", "kitchen", "admin")
@require_POST
def pos_update_item_status(request, order_id, item_id):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        data = request.POST
    status = data.get("status")
    if not status:
        return JsonResponse({"error": "status is required"}, status=400)
    OrderService.set_item_status(order_id, item_id, status)
    item = get_object_or_404(
        OrderItem.objects.select_related("order__table"),
        pk=item_id,
        order_id=order_id,
    )
    now = datetime.now(UTC)
    item.elapsed = _mins(now - item.created_at) if item.created_at else 0
    item.preparing = _mins(now - item.started_at) if item.started_at else None
    item.table_code = item.order.table.code if item.order.table else ""
    html = render_to_string(
        "pos/_kitchen_card.html",
        {
            "item": item,
            "is_admin": (
                request.user.is_superuser
                or (request.user.role and request.user.role.name == "admin")
            ),
        },
        request=request,
    )
    return HttpResponse(html)


@role_required("waiter", "admin")
def pos_product_options(request, product_id):
    """Devuelve la configuración de opciones de un producto para el modal POS."""
    product = get_object_or_404(Product, pk=product_id)
    return JsonResponse(MenuOptionService.pos_option_config(product))


@role_required("admin")
def audit_logs(request):
    from gourmet.apps.accounts.models import AuditLog

    logs = AuditLog.objects.select_related("user").all()[:200]
    return render(request, "pos/audit_logs.html", {"logs": logs})


MAX_CART_QTY = 99


def cart_key(table_code: str) -> str:
    return f"cart{table_code}"


def _line_id(product_id: UUID, option_value_ids: list[str]) -> str:
    normalized = sorted(str(value_id) for value_id in option_value_ids)
    raw = f"{product_id}:{':'.join(normalized)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _options_label(selected_options: list[dict]) -> str:
    if not selected_options:
        return ""

    return "; ".join(
        f"{option.get('group_name')}: {option.get('value_name')}"
        for option in selected_options
    )


def _get_cart_lines(request: HttpRequest, table_code: str) -> list[dict]:
    data = request.session.get(cart_key(table_code), {})

    if isinstance(data, dict) and "lines" in data:
        return data.get("lines", [])

    lines: list[dict] = []

    # Compatibilidad con carrito viejo: {product_id: quantity}
    if isinstance(data, dict):
        for product_id, quantity in data.items():
            try:
                parsed_product_id = UUID(str(product_id))
            except (TypeError, ValueError, AttributeError):
                continue

            try:
                parsed_quantity = int(quantity)
            except (TypeError, ValueError):
                continue

            if parsed_quantity <= 0:
                continue

            lines.append(
                {
                    "line_id": _line_id(parsed_product_id, []),
                    "product_id": str(parsed_product_id),
                    "quantity": min(parsed_quantity, MAX_CART_QTY),
                    "option_value_ids": [],
                    "unit_price": None,
                    "selected_options": [],
                }
            )

    return lines


def _save_cart_lines(
    request: HttpRequest,
    table_code: str,
    lines: list[dict],
) -> None:
    request.session[cart_key(table_code)] = {"lines": lines}
    request.session.modified = True


def _cart_context(request: HttpRequest, table_code: str) -> dict[str, Any]:
    lines = _get_cart_lines(request, table_code)
    now = django_tz.localtime()

    cart_lines: list[dict[str, Any]] = []
    cart_total = Decimal("0.00")
    cart_count = 0
    has_invalid = False

    for line in lines:
        try:
            raw_product_id = line.get("product_id")
            product_id = UUID(str(raw_product_id)) if raw_product_id else None

            if product_id is None:
                continue

            product = (
                Product.objects.select_related("category").filter(pk=product_id).first()
            )
            quantity = min(int(line.get("quantity", 1)), MAX_CART_QTY)
        except (TypeError, ValueError, AttributeError):
            continue

        option_value_ids = line.get("option_value_ids", [])
        stored_unit_price = Decimal(str(line.get("unit_price") or "0.00"))
        selected_options = line.get("selected_options", [])
        valid = True
        unit_price = stored_unit_price

        if product is None:
            valid = False
        else:
            if not MenuAvailabilityService.is_product_orderable(product, now):
                valid = False

            try:
                selected_options, price_delta = MenuOptionService.validate_selection(
                    product,
                    option_value_ids,
                )
                computed_price = (product.price + price_delta).quantize(Decimal("0.01"))

                if valid:
                    unit_price = computed_price
            except ValueError:
                valid = False

        if not valid:
            has_invalid = True

        line_total = unit_price * quantity
        cart_total += line_total
        cart_count += quantity

        cart_lines.append(
            {
                "line_id": line.get("line_id"),
                "product_id": line.get("product_id"),
                "product_name": product.name if product else "Producto no disponible",
                "quantity": quantity,
                "unit_price": unit_price,
                "total": line_total,
                "options": selected_options,
                "options_label": _options_label(selected_options),
                "invalid": not valid,
            }
        )

    return {
        "cart_lines": cart_lines,
        "cart_items": cart_lines,
        "cart_total": cart_total,
        "cart_count": cart_count,
        "has_invalid": has_invalid,
        "table_code": table_code,
    }


def _render_cart(request: HttpRequest, table_code: str) -> HttpResponse:
    return HttpResponse(
        render_to_string(
            "pos/_cart_summary.html",
            _cart_context(request, table_code),
            request=request,
        )
    )


def menu_public(request: HttpRequest, table_code: str) -> HttpResponse:
    """Vista pública del menú para autogestión por QR."""
    table = get_object_or_404(Table, code=table_code, is_active=True)
    now = django_tz.localtime()

    categories = (
        Category.objects.filter(is_active=True)
        .prefetch_related("availability_rules")
        .order_by("sort_order", "name")
    )

    available_categories = [
        category
        for category in categories
        if MenuAvailabilityService.is_category_available(category, now)
    ]

    products = (
        Product.objects.filter(category__in=available_categories)
        .select_related("category")
        .prefetch_related("tags")
        .order_by("category__sort_order", "sort_order", "name")
    )

    return render(
        request,
        "pos/customer_menu.html",
        {
            "table": table,
            "products": products,
            "categories": available_categories,
            **_cart_context(request, table_code),
        },
    )


def product_modal_public(
    request: HttpRequest,
    table_code: str,
    product_id: UUID,
) -> HttpResponse:
    get_object_or_404(Table, code=table_code, is_active=True)
    product = get_object_or_404(
        Product.objects.select_related("category").prefetch_related("tags"),
        pk=product_id,
    )

    now = django_tz.localtime()
    orderable = MenuAvailabilityService.is_product_orderable(product, now)
    attachments = MenuOptionService.get_product_attachments(product)

    groups = []
    conditions = []

    for attachment in attachments:
        group = attachment.option_group
        min_selections = group.min_selections

        if attachment.is_required and min_selections < 1:
            min_selections = 1

        groups.append(
            {
                "id": str(group.pk),
                "name": group.name,
                "required": attachment.is_required or min_selections > 0,
                "min": min_selections,
                "max": group.max_selections,
                "multiple": group.selection_type == "multiple",
            }
        )

        if attachment.condition_parent is not None:
            conditions.append(
                {
                    "group": str(group.pk),
                    "parent": str(attachment.condition_parent.option_group_id),
                    "values": [
                        str(condition_value.pk)
                        for condition_value in attachment.condition_values.all()
                    ],
                }
            )

    # PASAR EL DICCIONARIO DIRECTO, NO json.dumps
    modal_config = {
        "product_id": str(product.pk),
        "add_url": reverse("add_to_cart", kwargs={"table_code": table_code}),
        "base_price": str(product.price),
        "orderable": orderable,
        "groups": groups,
        "conditions": conditions,
    }

    return render(
        request,
        "pos/_product_modal.html",
        {
            "table_code": table_code,
            "product": product,
            "attachments": attachments,
            "orderable": orderable,
            "modal_config": modal_config,  # <-- CAMBIO AQUÍ: diccionario, no string
        },
    )


@require_POST
def add_to_cart(request: HttpRequest, table_code: str) -> HttpResponse:
    """Agrega producto al carrito (sesión) vía HTMX/fetch."""
    get_object_or_404(Table, code=table_code, is_active=True)

    raw_product_id = request.POST.get("product_id", "")
    raw_quantity = request.POST.get("quantity", "1")
    option_values = request.POST.getlist("option_values")

    try:
        product_id = UUID(str(raw_product_id))
        quantity = int(raw_quantity)
    except (TypeError, ValueError, AttributeError):
        return HttpResponse(status=400)

    if not 1 <= quantity <= MAX_CART_QTY:
        return HttpResponse(status=400)

    product = Product.objects.select_related("category").filter(pk=product_id).first()

    if product is None:
        return HttpResponse(status=400)

    if not MenuAvailabilityService.is_product_orderable(product):
        return HttpResponse(status=400)

    try:
        selected_options, price_delta = MenuOptionService.validate_selection(
            product,
            option_values,
        )
    except ValueError:
        return HttpResponse(status=400)

    unit_price = (product.price + price_delta).quantize(Decimal("0.01"))
    selected_ids = [str(option["value_id"]) for option in selected_options]
    line_key = _line_id(product_id, selected_ids)

    lines = _get_cart_lines(request, table_code)
    existing_line = next(
        (line for line in lines if line.get("line_id") == line_key),
        None,
    )

    if existing_line:
        existing_line["quantity"] = min(
            existing_line.get("quantity", 0) + quantity,
            MAX_CART_QTY,
        )
        existing_line["unit_price"] = str(unit_price)
        existing_line["selected_options"] = selected_options
    else:
        lines.append(
            {
                "line_id": line_key,
                "product_id": str(product_id),
                "quantity": quantity,
                "option_value_ids": selected_ids,
                "unit_price": str(unit_price),
                "selected_options": selected_options,
            }
        )

    _save_cart_lines(request, table_code, lines)
    return _render_cart(request, table_code)


@require_POST
def remove_from_cart(request: HttpRequest, table_code: str) -> HttpResponse:
    """Elimina una línea del carrito (sesión) vía HTMX."""
    get_object_or_404(Table, code=table_code, is_active=True)

    line_id = request.POST.get("line_id", "")
    lines = _get_cart_lines(request, table_code)

    if line_id:
        lines = [line for line in lines if line.get("line_id") != line_id]
    else:
        # Compatibilidad con eliminación vieja por product_id
        try:
            product_key = str(UUID(str(request.POST.get("product_id", ""))))
        except (TypeError, ValueError, AttributeError):
            return HttpResponse(status=400)

        lines = [line for line in lines if line.get("product_id") != product_key]

    _save_cart_lines(request, table_code, lines)
    return _render_cart(request, table_code)


@require_POST
def checkout_qr(request: HttpRequest, table_code: str) -> HttpResponse:
    """Confirma el pedido y lo envía a cocina."""
    table = get_object_or_404(Table, code=table_code, is_active=True)
    lines = _get_cart_lines(request, table_code)

    if not lines:
        messages.error(request, "El carrito está vacío")
        return redirect("menu_public", table_code=table_code)

    try:
        order = OrderService.create_from_cart_lines(
            table.pk,
            lines,
            notes="Pedido desde QR (autogestión)",
            source=Order.Source.QR,
        )
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("menu_public", table_code=table_code)
    except Exception as exc:
        messages.error(request, f"Error al crear el pedido: {exc}")
        return redirect("menu_public", table_code=table_code)

    request.session.pop(cart_key(table_code), None)
    request.session.modified = True

    messages.success(
        request,
        f"¡Pedido enviado a cocina! Orden #{str(order.pk)[:8]}",
    )

    return render(
        request,
        "pos/order_success.html",
        {"order": order, "table": table},
    )


@role_required("admin", "waiter")
def generate_qr_table(request: HttpRequest, table_code: str) -> HttpResponse:
    """Genera QR para una mesa específica."""
    img = qrcode.make(_qr_menu_url(request, table_code))
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return HttpResponse(buffer.getvalue(), content_type="image/png")


def _qr_menu_url(request: HttpRequest, table_code: str) -> str:
    return request.build_absolute_uri(
        reverse("menu_public", kwargs={"table_code": table_code})
    )


@role_required("admin", "waiter")
def print_qr_tables(request: HttpRequest) -> HttpResponse:
    """Vista para imprimir todos los QRs de las mesas."""
    tables = Table.objects.filter(is_active=True).order_by("code")
    tables_with_qr = [
        {"table": table, "url": _qr_menu_url(request, table.code)} for table in tables
    ]
    return render(
        request,
        "pos/print_qr_tables.html",
        {
            "tables": tables_with_qr,
            "business_name": settings.BUSINESS_NAME,
        },
    )
