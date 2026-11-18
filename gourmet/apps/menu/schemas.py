from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from ninja import Schema


class CategoryOut(Schema):
    id: UUID
    name: str
    description: str | None = None
    sort_order: int
    is_active: bool
    model_config = {"from_attributes": True}


class CategoryIn(Schema):
    name: str
    description: str | None = None
    sort_order: int = 0
    is_active: bool = True


class ProductOut(Schema):
    id: UUID
    category_id: UUID
    category_name: str
    name: str
    description: str | None = None
    price: Decimal
    tax_type: str = "INC_8"
    is_available: bool
    sort_order: int
    has_options: bool = False
    image_url: str = ""
    model_config = {"from_attributes": True}


class ProductIn(Schema):
    category_id: UUID
    name: str
    description: str | None = None
    price: Decimal
    tax_type: str = "INC_8"
    is_available: bool = True
    sort_order: int = 0
