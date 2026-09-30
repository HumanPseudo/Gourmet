from datetime import datetime
from decimal import Decimal
from uuid import UUID

from ninja import Schema


class OrderItemIn(Schema):
    product_id: UUID
    quantity: int = 1
    notes: str = ""
    discount_percent: Decimal = Decimal("0.00")


class OrderItemUpdate(Schema):
    quantity: int | None = None
    notes: str | None = None
    status: str | None = None
    discount_percent: Decimal | None = None


class OrderItemOut(Schema):
    id: UUID
    product_id: UUID | None
    product_name: str
    product_price: Decimal
    tax_rate: Decimal = Decimal("0.0000")
    discount_percent: Decimal = Decimal("0.00")
    quantity: int
    notes: str = ""
    status: str
    priority: int = 0
    started_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class PaymentIn(Schema):
    method: str
    amount: Decimal
    reference: str = ""
    tip: Decimal = Decimal("0.00")


class PaymentOut(Schema):
    id: UUID
    method: str
    amount: Decimal
    tip: Decimal
    reference: str
    created_at: datetime


class OrderCreateIn(Schema):
    table_id: UUID | None = None
    notes: str = ""


class OrderOut(Schema):
    id: UUID
    table_id: UUID | None
    status: str
    subtotal: Decimal
    total: Decimal
    discount_amount: Decimal
    notes: str = ""
    items: list[OrderItemOut]
    payments: list[PaymentOut]
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None


class KitchenItemOut(Schema):
    id: UUID
    order_id: UUID
    product_name: str
    product_price: Decimal
    quantity: int
    notes: str = ""
    status: str
    priority: int = 0
    started_at: datetime | None = None
    created_at: datetime
    table_code: str = ""


class PriorityIn(Schema):
    priority: int


class SplitItemIn(Schema):
    order_item_id: UUID
    quantity: int = 1


class SplitByItemsSplitIn(Schema):
    label: str
    items: list[SplitItemIn]


class SplitByItemsIn(Schema):
    method: str = "by_items"
    splits: list[SplitByItemsSplitIn]


class SplitByPercentageSplitIn(Schema):
    label: str
    percentage: Decimal


class SplitByPercentageIn(Schema):
    method: str = "by_percentage"
    splits: list[SplitByPercentageSplitIn]


class SplitEqualIn(Schema):
    method: str = "equal"
    n_splits: int
    labels: list[str]


class SplitItemOut(Schema):
    id: UUID
    order_item_id: UUID
    quantity: int


class SplitOut(Schema):
    id: UUID
    order_id: UUID
    label: str
    method: str
    percentage: Decimal
    amount: Decimal
    paid: bool
    items: list[SplitItemOut]
    created_at: datetime


class SplitPayIn(Schema):
    method: str
    reference: str = ""
    tip: Decimal = Decimal("0.00")
