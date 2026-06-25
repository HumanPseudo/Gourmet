from __future__ import annotations

import json

from django.test import TestCase, override_settings

from gourmet.apps.accounts.models import AuthToken, Role, User


@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"]
)
class AuthEndpointTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email="user@test.com",
            name="User",
            password="pass1234",
        )
        self.staff = User.objects.create_user(
            email="staff@test.com",
            name="Staff",
            password="pass1234",
            is_staff=True,
        )
        self.token = AuthToken.create_token(self.staff)

    def _post(self, path: str, data: dict, token: str | None = None) -> dict:
        headers = {"content_type": "application/json"}
        if token:
            headers["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        response = self.client.post(
            path, data=json.dumps(data), **headers  # type: ignore[arg-type]
        )
        return {"status": response.status_code, "data": response.json()}

    def _get(self, path: str, token: str | None = None) -> dict:
        headers = {}
        if token:
            headers["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        response = self.client.get(path, **headers)  # type: ignore[arg-type]
        return {"status": response.status_code, "data": response.json()}

    def _delete(self, path: str, token: str | None = None) -> dict:
        headers = {}
        if token:
            headers["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        response = self.client.delete(path, **headers)  # type: ignore[arg-type]
        return {"status": response.status_code, "data": response.json()}

    def test_register_creates_user_and_token(self) -> None:
        result = self._post(
            "/api/auth/register",
            {"email": "new@test.com", "name": "New", "password": "Pass1234!"},
        )
        assert result["status"] == 201
        assert "token" in result["data"]
        assert result["data"]["user"]["email"] == "new@test.com"
        assert User.objects.filter(email="new@test.com").exists()

    def test_register_returns_400_for_duplicate_email(self) -> None:
        result = self._post(
            "/api/auth/register",
            {"email": "user@test.com", "name": "Dup", "password": "Pass1234!"},
        )
        assert result["status"] == 400

    def test_register_returns_400_for_weak_password(self) -> None:
        result = self._post(
            "/api/auth/register",
            {"email": "weak@test.com", "name": "Weak", "password": "short"},
        )
        assert result["status"] == 400

    def test_login_with_valid_credentials(self) -> None:
        result = self._post(
            "/api/auth/login",
            {"email": "user@test.com", "password": "pass1234"},
        )
        assert result["status"] == 200
        assert "token" in result["data"]
        assert result["data"]["user"]["email"] == "user@test.com"

    def test_login_with_invalid_password(self) -> None:
        result = self._post(
            "/api/auth/login",
            {"email": "user@test.com", "password": "wrong"},
        )
        assert result["status"] == 401

    def test_login_with_nonexistent_email(self) -> None:
        result = self._post(
            "/api/auth/login",
            {"email": "nobody@test.com", "password": "pass1234"},
        )
        assert result["status"] == 401

    def test_logout_deletes_token(self) -> None:
        result = self._post("/api/auth/logout", {}, token=self.token.key)
        assert result["status"] == 200
        assert not AuthToken.objects.filter(key=self.token.key).exists()

    def test_me_returns_authenticated_user(self) -> None:
        result = self._get("/api/auth/me", token=self.token.key)
        assert result["status"] == 200
        assert result["data"]["email"] == "staff@test.com"

    def test_me_returns_401_without_token(self) -> None:
        result = self._get("/api/auth/me")
        assert result["status"] == 401


@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"]
)
class AdminEndpointTests(TestCase):
    def setUp(self) -> None:
        self.admin = User.objects.create_superuser(
            email="admin@test.com",
            password="admin1234",
            name="Admin",
        )
        self.token = AuthToken.create_token(self.admin)

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

    def _get(self, path: str, token: str | None = None) -> dict:
        headers = {}
        if token is None:
            token = self.token.key
        headers["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        response = self.client.get(path, **headers)  # type: ignore[arg-type]
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

    def test_create_role(self) -> None:
        result = self._post("/api/admin/roles", {"name": "Manager"})
        assert result["status"] == 201
        assert result["data"]["name"] == "Manager"

    def test_create_role_duplicate(self) -> None:
        Role.objects.create(name="Manager")
        result = self._post("/api/admin/roles", {"name": "Manager"})
        assert result["status"] == 400

    def test_list_roles(self) -> None:
        Role.objects.create(name="Cook")
        Role.objects.create(name="Server")
        result = self._get("/api/admin/roles")
        assert result["status"] == 200
        assert result["data"]["count"] == 2
        assert len(result["data"]["items"]) == 2

    def test_get_role(self) -> None:
        role = Role.objects.create(name="Bartender")
        result = self._get(f"/api/admin/roles/{role.pk}")
        assert result["status"] == 200
        assert result["data"]["name"] == "Bartender"

    def test_update_role(self) -> None:
        role = Role.objects.create(name="Old")
        result = self._put(
            f"/api/admin/roles/{role.pk}", {"name": "Updated"}
        )
        assert result["status"] == 200
        assert result["data"]["name"] == "Updated"

    def test_delete_role(self) -> None:
        role = Role.objects.create(name="Temp")
        result = self._delete(f"/api/admin/roles/{role.pk}")
        assert result["status"] == 200
        assert not Role.objects.filter(pk=role.pk).exists()

    def test_list_users(self) -> None:
        result = self._get("/api/admin/users")
        assert result["status"] == 200
        items = result["data"].get("items", result["data"])
        assert any(u["email"] == "admin@test.com" for u in items)

    def test_get_user(self) -> None:
        result = self._get(f"/api/admin/users/{self.admin.pk}")
        assert result["status"] == 200
        assert result["data"]["email"] == "admin@test.com"

    def test_non_staff_cannot_access_admin(self) -> None:
        user = User.objects.create_user(
            email="regular@test.com", password="pass1234"
        )
        user_token = AuthToken.create_token(user)
        result = self._get("/api/admin/roles", token=user_token.key)
        assert result["status"] == 403
