from __future__ import annotations

from typing import Any
from uuid import UUID

from django.http import HttpRequest
from ninja import Router
from ninja.pagination import paginate

from gourmet.apps.accounts.auth import AdminTokenAuth
from gourmet.apps.schemas import MessageOut

from .schemas import TableIn, TableOut
from .services import TableService

router = Router(auth=None)


# ── Table endpoints ────────────────────────────────────────────────────


@router.get("", response=list[TableOut], summary="List all tables")
@paginate
def list_tables(request: HttpRequest) -> Any:
    return TableService.list()


@router.post(
    "",
    auth=AdminTokenAuth(),
    response={201: TableOut, 400: MessageOut},
    summary="Create a table",
)
def create_table(
    request: HttpRequest, payload: TableIn
) -> tuple[int, TableOut] | tuple[int, dict[str, str]]:
    try:
        table = TableService.create(payload)
    except ValueError as e:
        return 400, {"detail": str(e)}
    return 201, TableOut.model_validate(table)


@router.get("/{table_id}", response=TableOut, summary="Get table by ID")
def get_table(request: HttpRequest, table_id: UUID) -> TableOut:
    return TableOut.model_validate(TableService.get(table_id))


@router.put(
    "/{table_id}",
    auth=AdminTokenAuth(),
    response={200: TableOut, 400: MessageOut},
    summary="Update a table",
)
def update_table(
    request: HttpRequest, table_id: UUID, payload: TableIn
) -> tuple[int, TableOut | dict[str, str]]:
    table = TableService.get(table_id)
    try:
        updated = TableService.update(table, payload)
    except ValueError as e:
        return 400, {"detail": str(e)}
    return 200, TableOut.model_validate(updated)


@router.delete(
    "/{table_id}",
    auth=AdminTokenAuth(),
    response=MessageOut,
    summary="Delete a table",
)
def delete_table(request: HttpRequest, table_id: UUID) -> dict[str, str]:
    table = TableService.get(table_id)
    TableService.delete(table)
    return {"detail": "Table deleted"}
