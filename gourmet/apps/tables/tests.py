from __future__ import annotations

import json

from django.test import TestCase

from gourmet.apps.accounts.models import AuthToken, User
from gourmet.apps.tables.models import Table


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
