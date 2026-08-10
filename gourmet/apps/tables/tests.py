from __future__ import annotations

import json

from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from gourmet.apps.accounts.models import AuthToken, User
from gourmet.apps.tables.models import Table, TableLayout, TableLayoutItem
from gourmet.apps.tables.services import TableLayoutService


class TableAPITests(TestCase):
    def setUp(self) -> None:
        self.admin = User.objects.create_superuser(
            email="admin@test.com",
            password="admin1234",
            name="Admin",
        )
        self.token = AuthToken.create_token(self.admin)
        self.table = Table.objects.create(code="T1", capacity=4)

    def _post(
        self, path: str, data: dict, token: str | None = None
    ) -> dict:
        headers = {"content_type": "application/json"}
        if token is None:
            token = self.token.key
        headers["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        response = self.client.post(
            path, data=json.dumps(data), **headers  # type: ignore[arg-type]
        )
        return {"status": response.status_code, "data": response.json()}

    def _get(self, path: str) -> dict:
        response = self.client.get(path)
        return {"status": response.status_code, "data": response.json()}

    def _put(
        self, path: str, data: dict, token: str | None = None
    ) -> dict:
        headers = {"content_type": "application/json"}
        if token is None:
            token = self.token.key
        headers["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        response = self.client.put(
            path, data=json.dumps(data), **headers  # type: ignore[arg-type]
        )
        return {"status": response.status_code, "data": response.json()}

    def _delete(self, path: str, token: str | None = None) -> dict:
        headers = {}
        if token is None:
            token = self.token.key
        headers["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        response = self.client.delete(path, **headers)  # type: ignore[arg-type]
        return {"status": response.status_code, "data": response.json()}

    def test_list_tables(self) -> None:
        Table.objects.create(code="T2", capacity=2)
        result = self._get("/api/tables")
        assert result["status"] == 200
        assert result["data"]["count"] == 2
        assert len(result["data"]["items"]) == 2

    def test_create_table(self) -> None:
        result = self._post("/api/tables", {"code": "T3", "capacity": 6})
        assert result["status"] == 201
        assert result["data"]["code"] == "T3"

    def test_create_table_duplicate_code(self) -> None:
        result = self._post("/api/tables", {"code": "T1"})
        assert result["status"] == 400

    def test_get_table(self) -> None:
        result = self._get(f"/api/tables/{self.table.pk}")
        assert result["status"] == 200
        assert result["data"]["code"] == "T1"

    def test_update_table(self) -> None:
        result = self._put(
            f"/api/tables/{self.table.pk}",
            {"code": "T1-Upd", "capacity": 6, "status": "cleaning"},
        )
        assert result["status"] == 200
        assert result["data"]["capacity"] == 6

    def test_delete_table(self) -> None:
        result = self._delete(f"/api/tables/{self.table.pk}")
        assert result["status"] == 200
        assert not Table.objects.filter(pk=self.table.pk).exists()

    def test_public_cannot_create_table(self) -> None:
        headers = {"content_type": "application/json"}
        response = self.client.post(
            "/api/tables",
            data=json.dumps({"code": "Hack", "capacity": 2}),
            **headers,  # type: ignore[arg-type]
        )
        assert response.status_code == 401


class TableLayoutModelTests(TestCase):
    def setUp(self) -> None:
        self.table1 = Table.objects.create(code="L1", capacity=4)
        self.table2 = Table.objects.create(code="L2", capacity=2)

    def test_save_positions_creates_items(self) -> None:
        layout = TableLayoutService.create("Salón", 800, 600)
        TableLayoutService.save_positions(
            layout,
            [
                {"table_id": str(self.table1.pk), "pos_x": 10, "pos_y": 20},
                {
                    "table_id": str(self.table2.pk),
                    "pos_x": 100,
                    "pos_y": 200,
                    "shape": "round",
                    "rotation": 90,
                },
            ],
        )
        self.assertEqual(layout.items.count(), 2)
        item2 = layout.items.get(table=self.table2)
        self.assertEqual(item2.shape, TableLayoutItem.Shape.ROUND)
        self.assertEqual(item2.rotation, 90)

    def test_save_positions_clamps_to_board_bounds(self) -> None:
        layout = TableLayoutService.create("Terraza", 100, 100)
        TableLayoutService.save_positions(
            layout,
            [{"table_id": str(self.table1.pk), "pos_x": 9999, "pos_y": -5}],
        )
        item = layout.items.get(table=self.table1)
        self.assertEqual(item.pos_x, 100)
        self.assertEqual(item.pos_y, 0)

    def test_save_positions_replaces_previous(self) -> None:
        layout = TableLayoutService.create("Salón", 800, 600)
        TableLayoutService.save_positions(
            layout, [{"table_id": str(self.table1.pk), "pos_x": 1, "pos_y": 1}]
        )
        TableLayoutService.save_positions(
            layout, [{"table_id": str(self.table2.pk), "pos_x": 2, "pos_y": 2}]
        )
        self.assertEqual(layout.items.count(), 1)
        self.assertEqual(layout.items.first().table, self.table2)  # type: ignore[union-attr]

    def test_unique_table_per_layout(self) -> None:
        layout = TableLayout.objects.create(name="Salón", width=800, height=600)
        TableLayoutItem.objects.create(layout=layout, table=self.table1)
        with self.assertRaises(IntegrityError):
            TableLayoutItem.objects.create(layout=layout, table=self.table1)


class TableLayoutViewTests(TestCase):
    def setUp(self) -> None:
        self.admin = User.objects.create_superuser(
            email="floor-admin@test.com",
            password="admin1234",
            name="Admin",
        )
        self.client.force_login(self.admin)
        self.table = Table.objects.create(code="F1", capacity=4)
        self.layout = TableLayoutService.create("Salón", 800, 600)

    def test_list_view(self) -> None:
        response = self.client.get(reverse("floor_layout_list"))
        assert response.status_code == 200
        assert self.layout.name in response.content.decode()

    def test_create_view(self) -> None:
        response = self.client.post(
            reverse("floor_layout_create"),
            {"name": "Terraza", "width": 500, "height": 400},
        )
        assert response.status_code == 302
        assert TableLayout.objects.filter(name="Terraza").exists()

    def test_edit_view_lists_available_tables(self) -> None:
        response = self.client.get(
            reverse("floor_layout_edit", args=[self.layout.pk])
        )
        assert response.status_code == 200
        assert self.table.code in response.content.decode()

    def test_save_positions_persists(self) -> None:
        response = self.client.post(
            reverse("floor_layout_save_positions", args=[self.layout.pk]),
            data=json.dumps(
                {
                    "items": [
                        {"table_id": str(self.table.pk), "pos_x": 30, "pos_y": 40}
                    ]
                }
            ),
            content_type="application/json",
        )
        assert response.status_code == 200
        assert response.json()["count"] == 1
        item = self.layout.items.get(table=self.table)
        assert item.pos_x == 30
        assert item.pos_y == 40

        # Reloading the editor reflects the persisted position
        response = self.client.get(
            reverse("floor_layout_edit", args=[self.layout.pk])
        )
        assert '"pos_x": 30' in response.content.decode()

    def test_delete_view(self) -> None:
        response = self.client.post(
            reverse("floor_layout_delete", args=[self.layout.pk])
        )
        assert response.status_code == 302
        assert not TableLayout.objects.filter(pk=self.layout.pk).exists()
