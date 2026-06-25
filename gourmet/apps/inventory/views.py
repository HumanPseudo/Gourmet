from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

from .models import InventoryItem
from .services import InventoryService


@staff_member_required
def inventory_list(request):
    items = InventoryItem.objects.all().order_by("name")
    low_stock = InventoryService.low_stock_items()
    return render(
        request, "pos/inventory.html",
        {"items": items, "low_stock": low_stock},
    )


@staff_member_required
def movement_list(request):
    return render(
        request, "pos/movements.html",
        {"movements": InventoryService.list_movements()},
    )


@staff_member_required
def recipe_list(request):
    return render(
        request, "pos/recipes.html",
        {"recipes": InventoryService.list_recipes()},
    )
