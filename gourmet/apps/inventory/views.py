from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

from .models import InventoryItem, InventoryMovement, ProductRecipe
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
    movements = (
        InventoryMovement.objects
        .select_related("item")
        .order_by("-created_at")
    )
    return render(request, "pos/movements.html", {"movements": movements})


@staff_member_required
def recipe_list(request):
    recipes = (
        ProductRecipe.objects
        .select_related("product__category", "item")
        .order_by("product__name", "item__name")
    )
    return render(request, "pos/recipes.html", {"recipes": recipes})
