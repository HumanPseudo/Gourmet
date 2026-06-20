from __future__ import annotations

import json

from django.test import TestCase

from gourmet.apps.accounts.models import AuthToken, User
from gourmet.apps.menu.models import Category, Product


class MenuAPITests(TestCase):
    def setUp(self) -> None:
        self.admin = User.objects.create_superuser(
            email="admin@test.com",
            password="admin1234",
            name="Admin",
        )
        self.token = AuthToken.create_token(self.admin)
        self.cat = Category.objects.create(name="Drinks", sort_order=1)

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

    def test_list_categories(self) -> None:
        Category.objects.create(name="Food", sort_order=0)
        result = self._get("/api/menu/categories")
        assert result["status"] == 200
        assert len(result["data"]) == 2

    def test_create_category(self) -> None:
        result = self._post("/api/menu/categories", {"name": "Desserts"})
        assert result["status"] == 201
        assert result["data"]["name"] == "Desserts"

    def test_create_category_duplicate(self) -> None:
        result = self._post("/api/menu/categories", {"name": "Drinks"})
        assert result["status"] == 400

    def test_get_category(self) -> None:
        result = self._get(f"/api/menu/categories/{self.cat.pk}")
        assert result["status"] == 200
        assert result["data"]["name"] == "Drinks"

    def test_update_category(self) -> None:
        result = self._put(
            f"/api/menu/categories/{self.cat.pk}",
            {"name": "Beverages", "sort_order": 1},
        )
        assert result["status"] == 200
        assert result["data"]["name"] == "Beverages"

    def test_delete_category(self) -> None:
        result = self._delete(f"/api/menu/categories/{self.cat.pk}")
        assert result["status"] == 200
        assert not Category.objects.filter(pk=self.cat.pk).exists()

    def test_list_products(self) -> None:
        Product.objects.create(
            category=self.cat, name="Cola", price="2.50"
        )
        result = self._get("/api/menu/products")
        assert result["status"] == 200
        assert len(result["data"]) == 1
        assert result["data"][0]["name"] == "Cola"

    def test_create_product(self) -> None:
        result = self._post(
            "/api/menu/products",
            {
                "category_id": str(self.cat.pk),
                "name": "Lemonade",
                "price": "3.00",
            },
        )
        assert result["status"] == 201
        assert result["data"]["name"] == "Lemonade"

    def test_get_product(self) -> None:
        product = Product.objects.create(
            category=self.cat, name="Water", price="1.50"
        )
        result = self._get(f"/api/menu/products/{product.pk}")
        assert result["status"] == 200
        assert result["data"]["name"] == "Water"

    def test_update_product(self) -> None:
        product = Product.objects.create(
            category=self.cat, name="Juice", price="2.00"
        )
        result = self._put(
            f"/api/menu/products/{product.pk}",
            {
                "category_id": str(self.cat.pk),
                "name": "Fresh Juice",
                "price": "2.50",
            },
        )
        assert result["status"] == 200
        assert result["data"]["name"] == "Fresh Juice"

    def test_delete_product(self) -> None:
        product = Product.objects.create(
            category=self.cat, name="Tea", price="1.00"
        )
        result = self._delete(f"/api/menu/products/{product.pk}")
        assert result["status"] == 200
        assert not Product.objects.filter(pk=product.pk).exists()

    def test_public_can_list_products(self) -> None:
        result = self._get("/api/menu/products")
        assert result["status"] == 200

    def test_public_cannot_create_product(self) -> None:
        headers = {"content_type": "application/json"}
        response = self.client.post(
            "/api/menu/products",
            data=json.dumps({"category_id": str(self.cat.pk), "name": "Hack", "price": "0"}),
            **headers,  # type: ignore[arg-type]
        )
        assert response.status_code == 401
