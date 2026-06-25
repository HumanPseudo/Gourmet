from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect, render

from gourmet.apps.menu.models import Product
from gourmet.apps.tables.models import Table

from .models import Order
from .services import OrderService


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
        OrderService.close(order_id)
        messages.success(request, "Orden cerrada")
        return redirect("order_list")
    return redirect("order_detail", order_id=order_id)
