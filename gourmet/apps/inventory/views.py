from collections import defaultdict
from decimal import Decimal

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from gourmet.apps.accounts.audit import log_audit

from .models import InventoryItem, InventoryMovement
from .services import InventoryService


@staff_member_required
def inventory_list(request):
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create":
            name = request.POST["name"].strip()
            if name:
                unit = request.POST.get("unit", "unit")
                stock = Decimal(request.POST.get("stock", "0"))
                min_stock = Decimal(request.POST.get("min_stock", "0"))
                cost = request.POST.get("cost_price") or None
                InventoryService.create_item(
                    name,
                    unit,
                    stock,
                    min_stock,
                    Decimal(cost) if cost else None,
                )
                log_audit(request, "inventory.create", name)
                messages.success(request, f"Insumo '{name}' creado")
        elif action == "edit":
            item = get_object_or_404(InventoryItem, pk=request.POST["item_id"])
            item.name = request.POST["name"].strip()
            item.unit = request.POST.get("unit", "unit")
            item.min_stock = Decimal(request.POST.get("min_stock", "0"))
            cp = request.POST.get("cost_price")
            item.cost_price = Decimal(cp) if cp else None
            item.save()
            messages.success(request, f"Insumo '{item.name}' actualizado")
        return HttpResponseRedirect(request.path)

    items = InventoryItem.objects.all().order_by("name")
    low_stock = InventoryService.low_stock_items()
    total_value = sum((i.stock * i.cost_price) for i in items if i.cost_price)
    return render(
        request,
        "pos/inventory.html",
        {"items": items, "low_stock": low_stock, "total_value": total_value},
    )


@staff_member_required
@require_POST
def inventory_adjust(request, item_id):
    item = get_object_or_404(InventoryItem, pk=item_id)
    qty = Decimal(request.POST["quantity"])
    ref = request.POST.get("reference", "")
    if qty > 0:
        item.stock += qty
        item.save(update_fields=["stock"])
        from .models import InventoryMovement

        InventoryMovement.objects.create(
            item=item,
            type=InventoryMovement.Type.IN,
            quantity=qty,
            reference=ref or "manual:in",
        )
        log_audit(request, "inventory.adjust", item.name, f"+{qty} {item.unit}")
        messages.success(request, f"+{qty} {item.unit} a '{item.name}'")
    elif qty < 0:
        removed = min(-qty, item.stock)
        item.stock -= removed
        item.save(update_fields=["stock"])
        from .models import InventoryMovement

        InventoryMovement.objects.create(
            item=item,
            type=InventoryMovement.Type.OUT,
            quantity=removed,
            reference=ref or "manual:out",
        )
        log_audit(request, "inventory.adjust", item.name, f"-{removed} {item.unit}")
        messages.success(request, f"{removed} {item.unit} de '{item.name}'")
    else:
        messages.warning(request, "Cantidad debe ser diferente de 0")
    return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/pos/inventory/"))


@staff_member_required
@require_POST
def inventory_delete(request, item_id):
    item = get_object_or_404(InventoryItem, pk=item_id)
    name = item.name
    item.delete()
    log_audit(request, "inventory.delete", name)
    messages.success(request, f"Insumo '{name}' eliminado")
    return HttpResponseRedirect("/pos/inventory/")


@staff_member_required
def movement_list(request):
    item_id = request.GET.get("item_id") or None
    movements = InventoryService.list_movements(item_id=item_id)
    return render(
        request,
        "pos/movements.html",
        {"movements": movements},
    )


@staff_member_required
def recipe_list(request):
    return render(
        request,
        "pos/recipes.html",
        {"recipes": InventoryService.list_recipes()},
    )


@staff_member_required
def used_today(request):
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    movements = InventoryMovement.objects.filter(
        created_at__gte=today_start, type=InventoryMovement.Type.OUT,
    ).select_related("item").order_by("item__name", "-created_at")

    summary = defaultdict(lambda: Decimal("0.000"))
    total_cost = Decimal("0")
    for m in movements:
        summary[m.item.name] += m.quantity
        if m.item.cost_price:
            total_cost += m.quantity * m.item.cost_price

    return render(request, "pos/used_today.html", {
        "movements": movements,
        "summary": dict(sorted(summary.items())),
        "total_cost": total_cost,
    })
