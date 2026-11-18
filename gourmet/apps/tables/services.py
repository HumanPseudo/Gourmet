from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from django.db import transaction
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404

from .models import Table, TableLayout, TableLayoutItem
from .schemas import TableIn


class TableService:
    @staticmethod
    def list() -> QuerySet[Table]:
        return Table.objects.all().order_by("code")

    @staticmethod
    def create(data: TableIn) -> Table:
        if Table.objects.filter(code=data.code).exists():
            raise ValueError("A table with this code already exists")
        return Table.objects.create(
            code=data.code,
            capacity=data.capacity,
            status=data.status,
            is_active=data.is_active,
        )

    @staticmethod
    def get(table_id: UUID) -> Table:
        return get_object_or_404(Table, pk=table_id)

    @staticmethod
    def update(table: Table, data: TableIn) -> Table:
        if data.code != table.code and Table.objects.filter(code=data.code).exists():
            raise ValueError("A table with this code already exists")
        table.code = data.code
        table.capacity = data.capacity
        table.status = data.status
        table.is_active = data.is_active
        table.save()
        return table

    @staticmethod
    def delete(table: Table) -> None:
        table.delete()

    @staticmethod
    def assign_waiter(table: Table, waiter_id: UUID | None) -> Table:
        table.assigned_waiter_id = waiter_id
        table.save(update_fields=["assigned_waiter"])
        return table


class TableLayoutService:
    @staticmethod
    def list() -> QuerySet[TableLayout]:
        return TableLayout.objects.all().order_by("name")

    @staticmethod
    def get(layout_id: UUID) -> TableLayout:
        return get_object_or_404(
            TableLayout.objects.prefetch_related("items__table"), pk=layout_id
        )

    @staticmethod
    def create(name: str, width: int, height: int) -> TableLayout:
        return TableLayout.objects.create(name=name, width=width, height=height)

    @staticmethod
    def update(
        layout: TableLayout, name: str, width: int, height: int
    ) -> TableLayout:
        layout.name = name
        layout.width = width
        layout.height = height
        layout.save()
        return layout

    @staticmethod
    @transaction.atomic
    def save_positions(
        layout: TableLayout, items: Sequence[dict[str, Any]]
    ) -> None:
        layout.items.all().delete()
        TableLayoutItem.objects.bulk_create(
            TableLayoutItem(
                layout=layout,
                table_id=item["table_id"],
                pos_x=max(0, min(int(item["pos_x"]), layout.width)),
                pos_y=max(0, min(int(item["pos_y"]), layout.height)),
                shape=item.get("shape") or TableLayoutItem.Shape.SQUARE,
                rotation=int(item.get("rotation") or 0),
            )
            for item in items
        )
