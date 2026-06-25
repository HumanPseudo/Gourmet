from typing import Any
from uuid import UUID

from django.http import HttpRequest
from ninja import Router
from ninja.pagination import paginate

from gourmet.apps.accounts.auth import TokenAuth
from gourmet.apps.schemas import MessageOut

from .schemas import (
    KitchenItemOut,
    OrderCreateIn,
    OrderItemIn,
    OrderItemOut,
    OrderItemUpdate,
    OrderOut,
    PaymentIn,
    PaymentOut,
)
from .services import OrderService

router = Router(tags=["Orders"], auth=TokenAuth())


@router.get("", response=list[OrderOut], summary="List orders")
@paginate
def list_orders(request: HttpRequest, status: str | None = None) -> Any:
    return OrderService.list(status=status)


@router.get("/active", response=list[OrderOut], summary="List active orders")
def list_active_orders(request: HttpRequest) -> Any:
    return [OrderOut.model_validate(o) for o in OrderService.list_active()]


@router.post(
    "",
    response={201: OrderOut},
    summary="Create an order",
)
def create_order(
    request: HttpRequest, payload: OrderCreateIn
) -> tuple[int, OrderOut]:
    order = OrderService.create(table_id=payload.table_id, notes=payload.notes)
    return 201, OrderOut.model_validate(order)


@router.get(
    "/{order_id}",
    response=OrderOut,
    summary="Get order detail",
)
def get_order(request: HttpRequest, order_id: UUID) -> OrderOut:
    return OrderOut.model_validate(OrderService.get(order_id))


@router.post(
    "/{order_id}/items",
    response={201: OrderItemOut, 400: MessageOut},
    summary="Add item to order",
)
def add_item(
    request: HttpRequest, order_id: UUID, payload: OrderItemIn
) -> tuple[int, Any]:
    try:
        item = OrderService.add_item(
            order_id, payload.product_id, payload.quantity, payload.notes,
        )
    except Exception as e:
        return 400, {"detail": str(e)}
    return 201, OrderItemOut.model_validate(item)


@router.patch(
    "/{order_id}/items/{item_id}",
    response=OrderItemOut,
    summary="Update order item",
)
def update_item(
    request: HttpRequest, order_id: UUID, item_id: UUID, payload: OrderItemUpdate
) -> OrderItemOut:
    item = OrderService.update_item(
        order_id, item_id, payload.quantity, payload.notes, payload.status
    )
    return OrderItemOut.model_validate(item)


@router.delete(
    "/{order_id}/items/{item_id}",
    response=MessageOut,
    summary="Remove item from order",
)
def remove_item(
    request: HttpRequest, order_id: UUID, item_id: UUID
) -> tuple[int, MessageOut]:
    OrderService.remove_item(order_id, item_id)
    return 200, MessageOut(detail="Item removed")


@router.post(
    "/{order_id}/checkout",
    response={200: OrderOut, 400: MessageOut},
    summary="Calculate order total",
)
def checkout(
    request: HttpRequest, order_id: UUID
) -> tuple[int, Any]:
    try:
        order = OrderService.checkout(order_id)
    except Exception as e:
        return 400, {"detail": str(e)}
    return 200, OrderOut.model_validate(order)


@router.post(
    "/{order_id}/pay",
    response={201: PaymentOut, 400: MessageOut},
    summary="Register payment",
)
def pay(
    request: HttpRequest, order_id: UUID, payload: PaymentIn
) -> tuple[int, Any]:
    try:
        payment = OrderService.pay(
            order_id, payload.method, payload.amount, payload.reference,
        )
    except ValueError as e:
        return 400, {"detail": str(e)}
    return 201, PaymentOut.model_validate(payment)


@router.post(
    "/{order_id}/cancel",
    response=OrderOut,
    summary="Cancel order",
)
def cancel_order(request: HttpRequest, order_id: UUID) -> OrderOut:
    return OrderOut.model_validate(OrderService.cancel(order_id))


@router.post(
    "/{order_id}/close",
    response={200: OrderOut, 400: MessageOut},
    summary="Close order",
)
def close_order(
    request: HttpRequest, order_id: UUID
) -> tuple[int, Any]:
    try:
        order = OrderService.close(order_id)
    except ValueError as e:
        return 400, {"detail": str(e)}
    return 200, OrderOut.model_validate(order)


# ── Kitchen endpoints ──────────────────────────────────────────────


@router.get(
    "/kitchen",
    response=list[KitchenItemOut],
    summary="List items for kitchen display",
)
def kitchen_items(request: HttpRequest) -> Any:
    items = OrderService.list_kitchen()
    return [KitchenItemOut.model_validate(i) for i in items]


@router.patch(
    "/{order_id}/items/{item_id}/status",
    response={200: OrderItemOut, 400: MessageOut},
    summary="Update item status (kitchen)",
)
def update_item_status(
    request: HttpRequest, order_id: UUID, item_id: UUID, payload: OrderItemUpdate
) -> tuple[int, Any]:
    if not payload.status:
        return 400, {"detail": "status is required"}
    item = OrderService.set_item_status(order_id, item_id, payload.status)
    return 200, OrderItemOut.model_validate(item)
