from datetime import datetime
from decimal import Decimal
from uuid import UUID

from ninja import Schema


class InventoryItemIn(Schema):
    name: str
    unit: str
    stock: Decimal = Decimal("0.000")
    min_stock: Decimal = Decimal("0.000")
    cost_price: Decimal | None = None


class InventoryItemOut(Schema):
    id: UUID
    name: str
    unit: str
    stock: Decimal
    min_stock: Decimal
    cost_price: Decimal | None
    created_at: datetime
    updated_at: datetime


class ProductRecipeIn(Schema):
    product_id: UUID
    item_id: UUID
    quantity: Decimal


class ProductRecipeOut(Schema):
    id: UUID
    product_id: UUID
    item_id: UUID
    quantity: Decimal


class InventoryMovementOut(Schema):
    id: UUID
    item_id: UUID
    type: str
    quantity: Decimal
    reference: str
    created_at: datetime
