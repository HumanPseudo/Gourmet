import json
from decimal import Decimal

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from gourmet.apps.menu.models import Product
from gourmet.apps.tables.models import Table

from .models import Order, OrderItem
from .services import OrderService


@staff_member_required
def pos(request):
    tables = Table.objects.filter(is_active=True).order_by("code")
    tax_choices = Product.TaxChoices.choices
    return render(
        request, "pos/pos.html",
        {"tables": tables, "tax_choices": tax_choices},
    )


@staff_member_required
@require_POST
def pos_create_order(request):
    data = json.loads(request.body)
    order = OrderService.create(
        table_id=data.get("table_id"), notes=data.get("notes", ""),
    )
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
    return JsonResponse({
        "id": str(order.pk),
        "subtotal": str(order.subtotal),
        "total": str(order.total),
        "tax_total": str(tax_total.quantize(Decimal("0.01"))),
        "total_paid": str(total_paid),
    })


@staff_member_required
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
        return JsonResponse({
            "id": str(payment.pk),
            "amount": str(payment.amount),
            "method": payment.method,
            "tip": str(payment.tip),
        })
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)


@staff_member_required
@require_POST
def pos_close(request, order_id):
    try:
        OrderService.close(order_id)
        return JsonResponse({"status": "closed"})
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)


@staff_member_required
def kitchen(request):
    items = OrderService.list_kitchen()
    return render(request, "pos/kitchen.html", {"items": items})


@staff_member_required
def order_list(request):
    orders = (
        Order.objects.all()
        .select_related("table")
        .prefetch_related("items", "payments")
    )
    return render(request, "pos/orders.html", {"orders": orders})


@staff_member_required
def order_detail(request, order_id):
    order = get_object_or_404(
        Order.objects.select_related("table").prefetch_related(
            "items__product", "payments",
        ),
        pk=order_id,
    )
    return render(request, "pos/order_detail.html", {"order": order})


@staff_member_required
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

        for pid, qty in zip(product_ids, quantities, strict=False):
            qty = int(qty)
            if qty > 0:
                OrderService.add_item(order.pk, pid, qty, "")

        messages.success(request, f"Orden #{str(order.pk)[:8]} creada")
        return redirect("order_detail", order_id=order.pk)

    return render(
        request, "pos/create_order.html",
        {"tables": tables, "products": products},
    )


@staff_member_required
def add_payment(request, order_id):
    get_object_or_404(Order, pk=order_id, status=Order.Status.OPEN)
    if request.method == "POST":
        method = request.POST["method"]
        amount = request.POST["amount"]
        reference = request.POST.get("reference", "")
        try:
            OrderService.pay(order_id, method, amount, reference)
            messages.success(request, "Pago registrado")
        except ValueError as e:
            messages.error(request, str(e))
        return redirect("order_detail", order_id=order_id)


@staff_member_required
def close_order(request, order_id):
    get_object_or_404(Order, pk=order_id, status=Order.Status.OPEN)
    if request.method == "POST":
        try:
            OrderService.close(order_id)
            messages.success(request, "Orden cerrada")
            return redirect("order_list")
        except ValueError as e:
            messages.error(request, str(e))
    return redirect("order_detail", order_id=order_id)


@staff_member_required
def dashboard(request):
    today = timezone.localdate()
    orders = Order.objects.filter(
        created_at__date=today, status=Order.Status.CLOSED,
    ).prefetch_related("payments", "items")

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

    return render(request, "pos/dashboard.html", {
        "today": today,
        "order_count": orders.count(),
        "total_sales": total_sales.quantize(Decimal("0.01")),
        "total_tax": total_tax.quantize(Decimal("0.01")),
        "total_tips": total_tips.quantize(Decimal("0.01")),
        "total_discount": total_discount.quantize(Decimal("0.01")),
        "by_method": by_method,
        "item_count": item_count,
        "top_products": top_sorted,
    })


@staff_member_required
@require_POST
def split_order(request, order_id):
    data = json.loads(request.body)
    item_ids = data.get("item_ids", [])
    if not item_ids:
        return JsonResponse({"error": "No items selected"}, status=400)
    order = get_object_or_404(Order, pk=order_id, status=Order.Status.OPEN)
    items_to_move = OrderItem.objects.filter(
        pk__in=item_ids, order=order,
        status__in=(OrderItem.Status.PENDING,),
    )
    if not items_to_move.exists():
        return JsonResponse({"error": "No movable items selected"}, status=400)
    new_order = Order.objects.create(
        table=order.table, notes=f"Split from {str(order.pk)[:8]}",
    )
    items_to_move.update(order=new_order)
    return JsonResponse({
        "new_order_id": str(new_order.pk),
        "moved": items_to_move.count(),
    })


@staff_member_required
def print_receipt(request, order_id):
    order = get_object_or_404(
        Order.objects.select_related("table").prefetch_related(
            "items__product", "payments",
        ),
        pk=order_id,
    )
    return render(request, "pos/print_receipt.html", {"order": order})


@staff_member_required
def print_kitchen(request, order_id):
    order = get_object_or_404(
        Order.objects.select_related("table").prefetch_related(
            "items__product",
        ),
        pk=order_id,
    )
    return render(
        request, "pos/print_kitchen.html",
        {"order": order, "now": timezone.now()},
    )
