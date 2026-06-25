from __future__ import annotations

from uuid import UUID

from django.db.models import QuerySet
from django.shortcuts import get_object_or_404

from .models import Table
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
