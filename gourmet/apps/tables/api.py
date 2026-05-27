from __future__ import annotations

from uuid import UUID

from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from ninja import Router, Schema

from gourmet.apps.accounts.auth import AdminTokenAuth

from .models import Table

router = Router(auth=None)


# ── Schemas ────────────────────────────────────────────────────────────


class TableOut(Schema):
    id: UUID
    code: str
    capacity: int
    status: str
    is_active: bool


class TableIn(Schema):
    code: str
    capacity: int = 4
    status: str = Table.Status.AVAILABLE
    is_active: bool = True


class MessageOut(Schema):
    detail: str


# ── Helpers ────────────────────────────────────────────────────────────


def table_to_out(t: Table) -> TableOut:
    return TableOut(
        id=t.pk,
        code=t.code,
        capacity=t.capacity,
        status=t.status,
        is_active=t.is_active,
    )


# ── Table endpoints ───────────────────────────────────────────────────


@router.get("", response=list[TableOut], summary="List all tables")
def list_tables(request: HttpRequest) -> list[TableOut]:
    return [table_to_out(t) for t in Table.objects.all().order_by("code")]


@router.post(
    "",
    auth=AdminTokenAuth(),
    response={201: TableOut, 400: MessageOut},
    summary="Create a table",
)
def create_table(
    request: HttpRequest, payload: TableIn
) -> tuple[int, TableOut] | tuple[int, dict[str, str]]:
    if Table.objects.filter(code=payload.code).exists():
        return 400, {"detail": "A table with this code already exists"}
    table = Table.objects.create(
        code=payload.code,
        capacity=payload.capacity,
        status=payload.status,
        is_active=payload.is_active,
    )
    return 201, table_to_out(table)


@router.get("/{table_id}", response=TableOut, summary="Get table by ID")
def get_table(request: HttpRequest, table_id: UUID) -> TableOut:
    table = get_object_or_404(Table, pk=table_id)
    return table_to_out(table)


@router.put(
    "/{table_id}",
    auth=AdminTokenAuth(),
    response=TableOut,
    summary="Update a table",
)
def update_table(request: HttpRequest, table_id: UUID, payload: TableIn) -> TableOut:
    table = get_object_or_404(Table, pk=table_id)
    table.code = payload.code
    table.capacity = payload.capacity
    table.status = payload.status
    table.is_active = payload.is_active
    table.save()
    return table_to_out(table)


@router.delete(
    "/{table_id}",
    auth=AdminTokenAuth(),
    response=MessageOut,
    summary="Delete a table",
)
def delete_table(request: HttpRequest, table_id: UUID) -> dict[str, str]:
    table = get_object_or_404(Table, pk=table_id)
    table.delete()
    return {"detail": "Table deleted"}
