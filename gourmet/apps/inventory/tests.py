from __future__ import annotations

import json
from decimal import Decimal

from django.test import TestCase

from gourmet.apps.accounts.models import AuthToken, User
from gourmet.apps.menu.models import Category, Product

from .models import InventoryItem, ProductRecipe


class InventoryAPITests(TestCase):
    def setUp(self) -> None:
        self.admin = User.objects.create_superuser(
            email="admin@test.com",
            password="admin1234",
            name="Admin",
        )
        self.token = AuthToken.create_token(self.admin)
        self.item = InventoryItem.objects.create(
            name="Flour", unit="kg", stock=Decimal("10.000"),
            min_stock=Decimal("2.000"), cost_price=Decimal("1.50"),
        )

    def _post(self, path: str, data: dict, token: str | None = None) -> dict:
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

    def _put(self, path: str, data: dict, token: str | None = None) -> dict:
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

    def test_list_items(self) -> None:
        InventoryItem.objects.create(name="Sugar", unit="kg", stock=Decimal("5"))
        result = self._get("/api/inventory/items")
        assert result["status"] == 200
        assert result["data"]["count"] == 2
        assert len(result["data"]["items"]) == 2

    def test_create_item(self) -> None:
        result = self._post(
            "/api/inventory/items",
            {"name": "Salt", "unit": "kg", "stock": "20.000"},
        )
        assert result["status"] == 201
        assert result["data"]["name"] == "Salt"

    def test_get_item(self) -> None:
        result = self._get(f"/api/inventory/items/{self.item.pk}")
        assert result["status"] == 200
        assert result["data"]["name"] == "Flour"

    def test_update_item(self) -> None:
        result = self._put(
            f"/api/inventory/items/{self.item.pk}",
            {"name": "Flour-1kg", "unit": "kg", "stock": "15.000",
             "min_stock": "3.000", "cost_price": "2.00"},
        )
        assert result["status"] == 200
        assert result["data"]["stock"] == "15.000"

    def test_delete_item(self) -> None:
        result = self._delete(f"/api/inventory/items/{self.item.pk}")
        assert result["status"] == 200
        assert not InventoryItem.objects.filter(pk=self.item.pk).exists()

    def test_low_stock(self) -> None:
        InventoryItem.objects.create(
            name="Low", unit="unit", stock=Decimal("1"), min_stock=Decimal("5"),
        )
        result = self._get("/api/inventory/items/low-stock")
        assert result["status"] == 200
        assert any(i["name"] == "Low" for i in result["data"])

    def test_non_admin_cannot_access(self) -> None:
        user = User.objects.create_user(
            email="user@test.com", password="pass1234",
        )
        user_token = AuthToken.create_token(user)
        result = self._post(
            "/api/inventory/items",
            {"name": "Hack", "unit": "kg", "stock": "1"},
            token=user_token.key,
        )
        assert result["status"] == 403

    def test_create_recipe(self) -> None:
        cat = Category.objects.create(name="Food")
        product = Product.objects.create(
            category=cat, name="Pizza", price=Decimal("10.00"),
        )
        result = self._post(
            "/api/inventory/recipes",
            {"product_id": str(product.pk), "item_id": str(self.item.pk),
             "quantity": "0.500"},
        )
        assert result["status"] == 201
        assert result["data"]["quantity"] == "0.500"

    def test_list_recipes(self) -> None:
        cat = Category.objects.create(name="Food")
        product = Product.objects.create(
            category=cat, name="Bread", price=Decimal("5.00"),
        )
        ProductRecipe.objects.create(
            product=product, item=self.item, quantity=Decimal("0.300"),
        )
        result = self._get("/api/inventory/recipes")
        assert result["status"] == 200
        assert result["data"]["count"] == 1

    def test_delete_recipe(self) -> None:
        cat = Category.objects.create(name="Food")
        product = Product.objects.create(
            category=cat, name="Cake", price=Decimal("15.00"),
        )
        recipe = ProductRecipe.objects.create(
            product=product, item=self.item, quantity=Decimal("0.200"),
        )
        result = self._delete(f"/api/inventory/recipes/{recipe.pk}")
        assert result["status"] == 200
        assert not ProductRecipe.objects.filter(pk=recipe.pk).exists()
