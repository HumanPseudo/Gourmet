from __future__ import annotations

import json
from decimal import Decimal

from django.test import TestCase

from gourmet.apps.accounts.models import AuthToken, User
from gourmet.apps.menu.models import Category, Product
from gourmet.apps.tables.models import Table

from .models import Order, OrderItem, Payment


class OrderAPITests(TestCase):
    def setUp(self) -> None:
        self.admin = User.objects.create_superuser(
            email="admin@test.com",
            password="admin1234",
            name="Admin",
        )
        self.token = AuthToken.create_token(self.admin)
        self.cat = Category.objects.create(name="Food")
        self.product = Product.objects.create(
            category=self.cat, name="Pizza", price=Decimal("10.00"),
        )
        self.table = Table.objects.create(code="T1", capacity=4)

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

    def _patch(self, path: str, data: dict, token: str | None = None) -> dict:
        headers = {"content_type": "application/json"}
        if token is None:
            token = self.token.key
        headers["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        response = self.client.patch(
            path, data=json.dumps(data), **headers,  # type: ignore[arg-type]
        )
        return {"status": response.status_code, "data": response.json()}

    def _delete(self, path: str, token: str | None = None) -> dict:
        headers = {}
        if token is None:
            token = self.token.key
        headers["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        response = self.client.delete(path, **headers)  # type: ignore[arg-type]
        return {"status": response.status_code, "data": response.json()}

    def _create_order(self) -> Order:
        return Order.objects.create(table=self.table)

    def test_create_order(self) -> None:
        result = self._post(
            "/api/orders",
            {"table_id": str(self.table.pk), "notes": "Extra napkins"},
        )
        assert result["status"] == 201
        assert result["data"]["notes"] == "Extra napkins"

    def test_list_orders(self) -> None:
        self._create_order()
        result = self._get("/api/orders")
        assert result["status"] == 200
        assert result["data"]["count"] == 1

    def test_list_active_orders(self) -> None:
        self._create_order()
        closed = Order.objects.create(
            table=self.table, status=Order.Status.CLOSED,
        )
        result = self._get("/api/orders/active")
        assert result["status"] == 200
        ids = [o["id"] for o in result["data"]]
        assert str(closed.pk) not in ids

    def test_get_order(self) -> None:
        order = self._create_order()
        result = self._get(f"/api/orders/{order.pk}")
        assert result["status"] == 200
        assert result["data"]["status"] == "open"

    def test_add_item(self) -> None:
        order = self._create_order()
        result = self._post(
            f"/api/orders/{order.pk}/items",
            {"product_id": str(self.product.pk), "quantity": 2, "notes": "No onion"},
        )
        assert result["status"] == 201
        assert result["data"]["product_name"] == "Pizza"
        assert result["data"]["quantity"] == 2

    def test_update_item(self) -> None:
        order = self._create_order()
        item = OrderItem.objects.create(
            order=order, product=self.product, product_name="Pizza",
            product_price=Decimal("10.00"), quantity=1,
        )
        result = self._patch(
            f"/api/orders/{order.pk}/items/{item.pk}",
            {"quantity": 3, "notes": "Extra cheese"},
        )
        assert result["status"] == 200
        assert result["data"]["quantity"] == 3

    def test_remove_item(self) -> None:
        order = self._create_order()
        item = OrderItem.objects.create(
            order=order, product=self.product, product_name="Pizza",
            product_price=Decimal("10.00"), quantity=1,
        )
        result = self._delete(f"/api/orders/{order.pk}/items/{item.pk}")
        assert result["status"] == 200
        assert not OrderItem.objects.filter(pk=item.pk).exists()

    def test_checkout(self) -> None:
        order = self._create_order()
        OrderItem.objects.create(
            order=order, product=self.product, product_name="Pizza",
            product_price=Decimal("10.00"), quantity=2,
        )
        result = self._post(f"/api/orders/{order.pk}/checkout", {})
        assert result["status"] == 200
        assert result["data"]["total"] == "20.00"

    def test_pay(self) -> None:
        order = self._create_order()
        result = self._post(
            f"/api/orders/{order.pk}/pay",
            {"method": "cash", "amount": "20.00", "reference": ""},
        )
        assert result["status"] == 201
        assert result["data"]["method"] == "cash"

    def test_close_success(self) -> None:
        order = self._create_order()
        OrderItem.objects.create(
            order=order, product=self.product, product_name="Pizza",
            product_price=Decimal("10.00"), quantity=1,
        )
        self._post(f"/api/orders/{order.pk}/checkout", {})
        Payment.objects.create(
            order=order, method="cash", amount=Decimal("10.00"),
        )
        result = self._post(f"/api/orders/{order.pk}/close", {})
        assert result["status"] == 200
        assert result["data"]["status"] == "closed"

    def test_close_fails_if_unpaid(self) -> None:
        order = self._create_order()
        OrderItem.objects.create(
            order=order, product=self.product, product_name="Pizza",
            product_price=Decimal("10.00"), quantity=1,
        )
        self._post(f"/api/orders/{order.pk}/checkout", {})
        result = self._post(f"/api/orders/{order.pk}/close", {})
        assert result["status"] == 400

    def test_cancel_order(self) -> None:
        order = self._create_order()
        result = self._post(f"/api/orders/{order.pk}/cancel", {})
        assert result["status"] == 200
        assert result["data"]["status"] == "cancelled"

    def test_kitchen_list(self) -> None:
        order = self._create_order()
        OrderItem.objects.create(
            order=order, product=self.product, product_name="Pizza",
            product_price=Decimal("10.00"), quantity=1,
            status=OrderItem.Status.PENDING,
        )
        result = self._get("/api/orders/kitchen")
        assert result["status"] == 200
        assert len(result["data"]) == 1

    def test_kitchen_update_status(self) -> None:
        order = self._create_order()
        item = OrderItem.objects.create(
            order=order, product=self.product, product_name="Pizza",
            product_price=Decimal("10.00"), quantity=1,
            status=OrderItem.Status.PENDING,
        )
        result = self._patch(
            f"/api/orders/{order.pk}/items/{item.pk}/status",
            {"status": "preparing"},
        )
        assert result["status"] == 200
        assert result["data"]["status"] == "preparing"

    def test_unauthorized_access(self) -> None:
        headers = {"content_type": "application/json"}
        response = self.client.post(
            "/api/orders",
            data=json.dumps({"notes": "Hack"}),
            **headers,  # type: ignore[arg-type]
        )
        assert response.status_code == 401
