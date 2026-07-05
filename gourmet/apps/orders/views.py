import csv
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone as django_tz
from django.views.decorators.http import require_POST

from gourmet.apps.accounts.audit import log_audit
from gourmet.apps.accounts.auth import role_required
from gourmet.apps.menu.models import Product
from gourmet.apps.tables.models import Table

from .models import DailyClose, Order, OrderItem
from .services import OrderService


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
            OrderService.add_item(
                order.pk,
                item["product_id"],
                item.get("quantity", 1),
                item.get("notes", ""),
                Decimal(str(item.get("discount_percent", 0))),
            )
        if data.get("checkout", True):
            order = OrderService.checkout(order.pk)
        total_paid = sum(p.amount for p in order.payments.all())
        tax_total = sum(
            (i.product_price * i.quantity * i.tax_rate)
            for i in order.items.exclude(status=OrderItem.Status.CANCELLED)
        )
        return JsonResponse(
            {
                "id": str(order.pk),
                "subtotal": str(order.subtotal),
                "total": str(order.total),
                "tax_total": str(tax_total.quantize(Decimal("0.01"))),
                "total_paid": str(total_paid),
            }
        )
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
        log_audit(request, "payment.added", f"Order {str(order_id)[:8]}",
                  f"{data['method']} ${data['amount']}")
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
        OrderService.add_item(
            order.pk,
            item["product_id"],
            item.get("quantity", 1),
            item.get("notes", ""),
            Decimal(str(item.get("discount_percent", 0))),
        )
    log_audit(request, "order.items_added", f"Order {str(order_id)[:8]}")
    order = OrderService.checkout(order.pk)
    total_paid = sum(p.amount for p in order.payments.all())
    tax_total = sum(
        (i.product_price * i.quantity * i.tax_rate)
        for i in order.items.exclude(status=OrderItem.Status.CANCELLED)
    )
    return JsonResponse(
        {
            "id": str(order.pk),
            "subtotal": str(order.subtotal),
            "total": str(order.total),
            "tax_total": str(tax_total.quantize(Decimal("0.01"))),
            "total_paid": str(total_paid),
        }
    )


@role_required("waiter", "admin")
@require_POST
def pos_close(request, order_id):
    try:
        OrderService.close(order_id)
        log_audit(request, "order.closed", f"Order {str(order_id)[:8]}")
        return JsonResponse({"status": "closed"})
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)


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
    order = get_object_or_404(
        Order.objects.select_related("table").prefetch_related(
            "items__product",
            "payments",
        ),
        pk=order_id,
    )
    total_paid = sum(p.amount for p in order.payments.all())
    return render(
        request,
        "pos/order_detail.html",
        {
            "order": order,
            "total_paid": total_paid,
            "pending": order.total - total_paid,
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
            log_audit(request, "payment.added", f"Order {str(order_id)[:8]}",
                      f"{method} ${amount}")
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
        log_audit(request, "daily_close.saved",
                  f"cash={total_cash} counted={cash_counted} diff={diff}")
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
    log_audit(request, "order.splitted",
              f"Order {str(order_id)[:8]} → {str(new_order.pk)[:8]}")
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


@role_required("admin")
def audit_logs(request):
    from gourmet.apps.accounts.models import AuditLog

    logs = AuditLog.objects.select_related("user").all()[:200]
    return render(request, "pos/audit_logs.html", {"logs": logs})


def menu_public(request):
    products = (
        Product.objects.filter(is_available=True)
        .select_related("category")
        .order_by("category__sort_order", "sort_order", "name")
    )
    categories = {p.category for p in products if p.category}
    sorted_cats = sorted(categories, key=lambda c: c.sort_order)
    return render(
        request,
        "pos/customer_menu.html",
        {"products": products, "categories": sorted_cats},
    )
