from __future__ import annotations

from uuid import UUID

from ninja import Schema


class TableOut(Schema):
    id: UUID
    code: str
    capacity: int
    status: str
    is_active: bool
    model_config = {"from_attributes": True}


class TableIn(Schema):
    code: str
    capacity: int = 4
    status: str = "available"
    is_active: bool = True
