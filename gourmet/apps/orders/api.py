from typing import Any
from uuid import UUID

from django.http import HttpRequest
from ninja import Router
from ninja.pagination import paginate

from gourmet.apps.accounts.auth import RoleTokenAuth, TokenAuth
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
    PriorityIn,
    SplitByItemsIn,
    SplitByPercentageIn,
    SplitEqualIn,
    SplitItemOut,
    SplitOut,
    SplitPayIn,
)
from .services import OrderService

router = Router(tags=["Orders"], auth=TokenAuth())


@router.get("", response=list[OrderOut], summary="List orders")
@paginate
def list_orders(request: HttpRequest, status: str | None = None) -> Any:
    return OrderService.list_orders(status=status)


@router.get("/active", response=list[OrderOut], summary="List active orders")
def list_active_orders(request: HttpRequest) -> Any:
    return [OrderOut.model_validate(o) for o in OrderService.list_active()]


@router.post(
    "",
    response={201: OrderOut},
    summary="Create an order",
)
def create_order(request: HttpRequest, payload: OrderCreateIn) -> tuple[int, OrderOut]:
    order = OrderService.create(table_id=payload.table_id, notes=payload.notes)
    return 201, OrderOut.model_validate(order)


# ── Kitchen endpoints (before param routes) ─────────────────────────


@router.get(
    "/kitchen",
    response=list[KitchenItemOut],
    summary="List items for kitchen display",
)
def kitchen_items(request: HttpRequest) -> Any:
    items = OrderService.list_kitchen()
    result = []
    for i in items:
        out = KitchenItemOut.model_validate(i)
        out.table_code = i.order.table.code if i.order.table else ""
        result.append(out)
    return result


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
            order_id,
            payload.product_id,
            payload.quantity,
            payload.notes,
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
def checkout(request: HttpRequest, order_id: UUID) -> tuple[int, Any]:
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
def pay(request: HttpRequest, order_id: UUID, payload: PaymentIn) -> tuple[int, Any]:
    try:
        payment = OrderService.pay(
            order_id,
            payload.method,
            payload.amount,
            payload.reference,
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


@router.patch(
    "/items/{item_id}/priority",
    response={200: OrderItemOut, 400: MessageOut},
    auth=RoleTokenAuth("admin"),
    summary="Set item priority (kitchen reorder)",
)
def set_item_priority(
    request: HttpRequest, item_id: UUID, payload: PriorityIn
) -> tuple[int, Any]:
    item = OrderService.set_item_priority(item_id, payload.priority)
    return 200, OrderItemOut.model_validate(item)


@router.post(
    "/{order_id}/close",
    response={200: OrderOut, 400: MessageOut},
    summary="Close order",
)
def close_order(request: HttpRequest, order_id: UUID) -> tuple[int, Any]:
    try:
        order = OrderService.close(order_id)
    except ValueError as e:
        return 400, {"detail": str(e)}
    return 200, OrderOut.model_validate(order)


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


# ── Bill Splitting ───────────────────────────────────────────────


def _split_to_out(split: Any) -> SplitOut:
    out = SplitOut.model_validate(split)
    out.items = [
        SplitItemOut(id=bi.pk, order_item_id=bi.order_item_id, quantity=bi.quantity)
        for bi in split.items.all()
    ]
    return out


@router.get(
    "/{order_id}/splits",
    response=list[SplitOut],
    summary="List splits for an order",
)
def list_splits(request: HttpRequest, order_id: UUID) -> list[SplitOut]:
    return [_split_to_out(s) for s in OrderService.get_splits(order_id)]


@router.post(
    "/{order_id}/splits",
    response={201: list[SplitOut], 400: MessageOut},
    summary="Create splits for an order",
)
def create_splits(
    request: HttpRequest,
    order_id: UUID,
    payload: SplitByItemsIn | SplitByPercentageIn | SplitEqualIn,
) -> tuple[int, Any]:
    data = payload.model_dump()
    method = data.get("method", "by_items")
    if method not in ("by_items", "by_percentage", "equal"):
        return 400, {"detail": f"Invalid method: {method}"}
    try:
        if method == "equal":
            splits = OrderService.split_equal(
                order_id, data["n_splits"], data["labels"],
            )
        elif method == "by_percentage":
            splits = OrderService.split_by_percentage(order_id, data["splits"])
        else:
            splits = OrderService.split_by_items(order_id, data["splits"])
    except ValueError as e:
        return 400, {"detail": str(e)}
    return 201, [_split_to_out(s) for s in splits]


@router.post(
    "/{order_id}/splits/{split_id}/pay",
    response={200: SplitOut, 400: MessageOut},
    summary="Pay a split",
)
def pay_split(
    request: HttpRequest,
    order_id: UUID,
    split_id: UUID,
    payload: SplitPayIn,
) -> tuple[int, Any]:
    try:
        split = OrderService.mark_split_paid(
            split_id, payload.method, payload.reference, payload.tip,
            order_id=order_id,
        )
    except ValueError as e:
        return 400, {"detail": str(e)}
    return 200, _split_to_out(split)


@router.delete(
    "/{order_id}/splits/{split_id}",
    response={200: MessageOut, 400: MessageOut},
    summary="Delete a split",
)
def delete_split(
    request: HttpRequest, order_id: UUID, split_id: UUID,
) -> tuple[int, MessageOut]:
    try:
        OrderService.delete_split(split_id, order_id=order_id)
    except ValueError as e:
        return 400, MessageOut(detail=str(e))
    return 200, MessageOut(detail="Split deleted")
