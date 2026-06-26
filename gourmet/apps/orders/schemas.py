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
    created_at: datetime
