from typing import Any
from uuid import UUID

from django.http import HttpRequest
from ninja import Router
from ninja.pagination import paginate

from gourmet.apps.accounts.auth import AdminTokenAuth
from gourmet.apps.schemas import MessageOut

from .schemas import (
    InventoryItemIn,
    InventoryItemOut,
    InventoryMovementOut,
    ProductRecipeIn,
    ProductRecipeOut,
)
from .services import InventoryService

router = Router(tags=["Inventory"], auth=AdminTokenAuth())


@router.get(
    "/items",
    response=list[InventoryItemOut],
    summary="List inventory items",
)
@paginate
def list_items(request: HttpRequest) -> Any:
    return InventoryService.list_items()


@router.get(
    "/items/low-stock",
    response=list[InventoryItemOut],
    summary="List low stock items",
)
def low_stock_items(request: HttpRequest) -> Any:
    return [
        InventoryItemOut.model_validate(i) for i in InventoryService.low_stock_items()
    ]


@router.post(
    "/items",
    response={201: InventoryItemOut, 400: MessageOut},
    summary="Create inventory item",
)
def create_item(
    request: HttpRequest, payload: InventoryItemIn
) -> tuple[int, Any]:
    try:
        item = InventoryService.create_item(
            name=payload.name,
            unit=payload.unit,
            stock=payload.stock,
            min_stock=payload.min_stock,
            cost_price=payload.cost_price,
        )
    except Exception as e:
        return 400, {"detail": str(e)}
    return 201, InventoryItemOut.model_validate(item)


@router.get(
    "/items/{item_id}",
    response=InventoryItemOut,
    summary="Get inventory item",
)
def get_item(request: HttpRequest, item_id: UUID) -> InventoryItemOut:
    return InventoryItemOut.model_validate(InventoryService.get_item(item_id))


@router.put(
    "/items/{item_id}",
    response=InventoryItemOut,
    summary="Update inventory item",
)
def update_item(
    request: HttpRequest, item_id: UUID, payload: InventoryItemIn
) -> InventoryItemOut:
    item = InventoryService.update_item(
        item_id,
        name=payload.name,
        unit=payload.unit,
        stock=payload.stock,
        min_stock=payload.min_stock,
        cost_price=payload.cost_price,
    )
    return InventoryItemOut.model_validate(item)


@router.delete(
    "/items/{item_id}",
    response=MessageOut,
    summary="Delete inventory item",
)
def delete_item(request: HttpRequest, item_id: UUID) -> tuple[int, MessageOut]:
    InventoryService.delete_item(item_id)
    return 200, MessageOut(detail="Item deleted")


# ── Recipes ───────────────────────────────────────────────────────


@router.get(
    "/recipes",
    response=list[ProductRecipeOut],
    summary="List product recipes",
)
@paginate
def list_recipes(request: HttpRequest) -> Any:
    return InventoryService.list_recipes()


@router.post(
    "/recipes",
    response={201: ProductRecipeOut, 400: MessageOut},
    summary="Create product recipe",
)
def create_recipe(
    request: HttpRequest, payload: ProductRecipeIn
) -> tuple[int, Any]:
    try:
        recipe = InventoryService.create_recipe(
            payload.product_id, payload.item_id, payload.quantity
        )
    except Exception as e:
        return 400, {"detail": str(e)}
    return 201, ProductRecipeOut.model_validate(recipe)


@router.delete(
    "/recipes/{recipe_id}",
    response=MessageOut,
    summary="Delete product recipe",
)
def delete_recipe(request: HttpRequest, recipe_id: UUID) -> tuple[int, MessageOut]:
    InventoryService.delete_recipe(recipe_id)
    return 200, MessageOut(detail="Recipe deleted")


# ── Movements ─────────────────────────────────────────────────────


@router.get(
    "/movements",
    response=list[InventoryMovementOut],
    summary="List inventory movements",
)
@paginate
def list_movements(
    request: HttpRequest, item_id: UUID | None = None
) -> Any:
    return InventoryService.list_movements(item_id=item_id)
