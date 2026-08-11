from __future__ import annotations

import json
import uuid
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from gourmet.apps.accounts.models import AuthToken, User
from gourmet.apps.menu.models import Category, Product
from gourmet.apps.tables.models import Table, TableLayout, TableLayoutItem

from .models import BillSplit, BillSplitItem, Order, OrderItem, Payment
from .services import OrderService


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

    def test_close_succeeds_even_if_unpaid(self) -> None:
        order = self._create_order()
        OrderItem.objects.create(
            order=order, product=self.product, product_name="Pizza",
            product_price=Decimal("10.00"), quantity=1,
        )
        self._post(f"/api/orders/{order.pk}/checkout", {})
        result = self._post(f"/api/orders/{order.pk}/close", {})
        assert result["status"] == 200

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


class BillSplitTests(TestCase):
    """Tests for the bill splitting feature."""

    def setUp(self) -> None:
        self.admin = User.objects.create_superuser(
            email="admin@test.com", password="admin1234", name="Admin",
        )
        self.token = AuthToken.create_token(self.admin)
        self.cat = Category.objects.create(name="Food")
        self.product1 = Product.objects.create(
            category=self.cat, name="Pizza", price=Decimal("10.00"),
        )
        self.product2 = Product.objects.create(
            category=self.cat, name="Pasta", price=Decimal("15.00"),
        )
        self.table = Table.objects.create(code="T1", capacity=4)

    def _create_order_with_items(self) -> tuple[Order, OrderItem, OrderItem]:
        order = Order.objects.create(table=self.table)
        item1 = OrderItem.objects.create(
            order=order, product=self.product1, product_name="Pizza",
            product_price=Decimal("10.00"), quantity=2, tax_rate=Decimal("0.08"),
        )
        item2 = OrderItem.objects.create(
            order=order, product=self.product2, product_name="Pasta",
            product_price=Decimal("15.00"), quantity=1, tax_rate=Decimal("0.08"),
        )
        # Checkout to compute totals: subtotal = 10*2 + 15 = 35, total = 35*1.08 = 37.80
        OrderService.checkout(order.pk)
        order.refresh_from_db()
        return order, item1, item2

    def _post(self, path: str, data: dict) -> dict:
        auth = f"Bearer {self.token.key}"
        headers = {
            "content_type": "application/json",
            "HTTP_AUTHORIZATION": auth,
        }
        response = self.client.post(path, data=json.dumps(data), **headers)  # type: ignore[arg-type]
        return {"status": response.status_code, "data": response.json()}

    def _get(self, path: str) -> dict:
        response = self.client.get(path, HTTP_AUTHORIZATION=f"Bearer {self.token.key}")
        return {"status": response.status_code, "data": response.json()}

    def _delete(self, path: str) -> dict:
        auth = f"Bearer {self.token.key}"
        response = self.client.delete(
            path, HTTP_AUTHORIZATION=auth
        )
        return {"status": response.status_code, "data": response.json()}

    # ── Service-level tests ──────────────────────────────────────

    def test_split_by_items_service(self) -> None:
        order, item1, item2 = self._create_order_with_items()
        splits = OrderService.split_by_items(order.pk, [
            {
                "label": "Juan",
                "items": [{"order_item_id": str(item1.pk), "quantity": 1}],
            },
            {
                "label": "Ana",
                "items": [
                    {"order_item_id": str(item1.pk), "quantity": 1},
                    {"order_item_id": str(item2.pk), "quantity": 1},
                ],
            },
        ])
        assert len(splits) == 2
        assert splits[0].label == "Juan"
        assert splits[1].label == "Ana"
        assert splits[0].method == BillSplit.Method.BY_ITEMS
        # Juan gets 1 pizza at $10 with 8% tax = $10.80
        assert splits[0].amount == Decimal("10.80")
        # Ana gets 1 pizza ($10) + 1 pasta ($15) with 8% tax = $27.00
        assert splits[1].amount == Decimal("27.00")
        # Check split items
        assert BillSplitItem.objects.filter(split=splits[0]).count() == 1
        assert BillSplitItem.objects.filter(split=splits[1]).count() == 2

    def test_split_by_items_validation_exceeds_quantity(self) -> None:
        order, item1, item2 = self._create_order_with_items()
        with self.assertRaises(ValueError) as ctx:
            OrderService.split_by_items(order.pk, [
                {
                    "label": "Juan",
                    "items": [{"order_item_id": str(item1.pk), "quantity": 5}],
                },
            ])
        assert "exceeds" in str(ctx.exception)

    def test_split_by_items_validation_invalid_item(self) -> None:
        order, item1, item2 = self._create_order_with_items()
        fake_id = uuid.uuid4()
        with self.assertRaises(ValueError):
            OrderService.split_by_items(order.pk, [
                {
                    "label": "Juan",
                    "items": [{"order_item_id": str(fake_id), "quantity": 1}],
                },
            ])

    def test_split_by_percentage_service(self) -> None:
        order, _, _ = self._create_order_with_items()
        # total is 37.80
        splits = OrderService.split_by_percentage(order.pk, [
            {"label": "Juan", "percentage": 60},
            {"label": "Ana", "percentage": 40},
        ])
        assert len(splits) == 2
        assert splits[0].percentage == Decimal("60")
        assert splits[1].percentage == Decimal("40")
        assert splits[0].method == BillSplit.Method.BY_PERCENTAGE
        # 37.80 * 60% = 22.68
        assert splits[0].amount == Decimal("22.68")
        # 37.80 * 40% = 15.12
        assert splits[1].amount == Decimal("15.12")

    def test_split_by_percentage_validation(self) -> None:
        order, _, _ = self._create_order_with_items()
        with self.assertRaises(ValueError) as ctx:
            OrderService.split_by_percentage(order.pk, [
                {"label": "Juan", "percentage": 50},
                {"label": "Ana", "percentage": 30},
            ])
        assert "100" in str(ctx.exception)

    def test_split_equal_service(self) -> None:
        order, _, _ = self._create_order_with_items()
        # total is 37.80
        splits = OrderService.split_equal(order.pk, 3, ["A", "B", "C"])
        assert len(splits) == 3
        assert all(s.method == BillSplit.Method.EQUAL for s in splits)
        assert splits[0].amount == Decimal("12.60")
        assert splits[1].amount == Decimal("12.60")
        # Last one gets the remainder
        assert splits[2].amount == Decimal("12.60")

    def test_split_equal_validation(self) -> None:
        order, _, _ = self._create_order_with_items()
        with self.assertRaises(ValueError):
            OrderService.split_equal(order.pk, 1, ["A"])
        with self.assertRaises(ValueError):
            OrderService.split_equal(order.pk, 2, ["A"])

    def test_get_splits(self) -> None:
        order, item1, _ = self._create_order_with_items()
        OrderService.split_by_items(order.pk, [
            {
                "label": "Juan",
                "items": [
                    {"order_item_id": str(item1.pk), "quantity": 2}
                ],
            },
        ])
        splits = OrderService.get_splits(order.pk)
        assert splits.count() == 1

    def test_mark_split_paid(self) -> None:
        order, item1, _ = self._create_order_with_items()
        splits = OrderService.split_by_items(order.pk, [
            {
                "label": "Juan",
                "items": [
                    {"order_item_id": str(item1.pk), "quantity": 2}
                ],
            },
        ])
        split = splits[0]
        paid = OrderService.mark_split_paid(
            split.pk, "cash", "ref-001", Decimal("2.00")
        )
        assert paid.paid is True
        # Payment should be created
        payment = Payment.objects.filter(order=order, amount=split.amount).first()
        assert payment is not None
        assert payment.method == "cash"
        assert payment.tip == Decimal("2.00")

    def test_mark_split_paid_already_paid(self) -> None:
        order, item1, _ = self._create_order_with_items()
        splits = OrderService.split_by_items(order.pk, [
            {
                "label": "Juan",
                "items": [
                    {"order_item_id": str(item1.pk), "quantity": 2}
                ],
            },
        ])
        OrderService.mark_split_paid(splits[0].pk, "cash")
        with self.assertRaises(ValueError) as ctx:
            OrderService.mark_split_paid(splits[0].pk, "card")
        assert "already paid" in str(ctx.exception)

    def test_delete_split(self) -> None:
        order, item1, _ = self._create_order_with_items()
        splits = OrderService.split_by_items(order.pk, [
            {
                "label": "Juan",
                "items": [
                    {"order_item_id": str(item1.pk), "quantity": 2}
                ],
            },
        ])
        split_id = splits[0].pk
        OrderService.delete_split(split_id)
        assert not BillSplit.objects.filter(pk=split_id).exists()

    def test_delete_split_paid(self) -> None:
        order, item1, _ = self._create_order_with_items()
        splits = OrderService.split_by_items(order.pk, [
            {
                "label": "Juan",
                "items": [
                    {"order_item_id": str(item1.pk), "quantity": 2}
                ],
            },
        ])
        OrderService.mark_split_paid(splits[0].pk, "cash")
        with self.assertRaises(ValueError) as ctx:
            OrderService.delete_split(splits[0].pk)
        assert "paid" in str(ctx.exception)

    # ── API-level tests ──────────────────────────────────────────

    def test_api_list_splits_empty(self) -> None:
        order, _, _ = self._create_order_with_items()
        result = self._get(f"/api/orders/{order.pk}/splits")
        assert result["status"] == 200
        assert result["data"] == []

    def test_api_create_split_equal(self) -> None:
        order, _, _ = self._create_order_with_items()
        result = self._post(f"/api/orders/{order.pk}/splits", {
            "n_splits": 2,
            "labels": ["Persona 1", "Persona 2"],
        })
        assert result["status"] == 201
        assert len(result["data"]) == 2
        assert result["data"][0]["method"] == "equal"

    def test_api_create_split_by_percentage(self) -> None:
        order, _, _ = self._create_order_with_items()
        result = self._post(f"/api/orders/{order.pk}/splits", {
            "splits": [
                {"label": "Juan", "percentage": 50},
                {"label": "Ana", "percentage": 50},
            ],
        })
        assert result["status"] == 201
        assert len(result["data"]) == 2
        assert result["data"][0]["method"] == "by_percentage"

    def test_api_create_split_by_items(self) -> None:
        order, item1, item2 = self._create_order_with_items()
        result = self._post(f"/api/orders/{order.pk}/splits", {
            "splits": [
                {
                "label": "Juan",
                "items": [
                    {"order_item_id": str(item1.pk), "quantity": 1}
                ],
            },
                {
                "label": "Ana",
                "items": [
                    {"order_item_id": str(item1.pk), "quantity": 1},
                    {"order_item_id": str(item2.pk), "quantity": 1},
                ],
            },
            ],
        })
        assert result["status"] == 201
        assert len(result["data"]) == 2
        assert result["data"][0]["method"] == "by_items"

    def test_api_split_validation_error(self) -> None:
        order, _, _ = self._create_order_with_items()
        result = self._post(f"/api/orders/{order.pk}/splits", {
            "splits": [
                {"label": "Juan", "percentage": 50},
            ],
        })
        assert result["status"] == 400

    def test_api_pay_split(self) -> None:
        order, item1, _ = self._create_order_with_items()
        # Create a split via service
        splits = OrderService.split_by_items(order.pk, [
            {
                "label": "Juan",
                "items": [
                    {"order_item_id": str(item1.pk), "quantity": 2}
                ],
            },
        ])
        split_id = str(splits[0].pk)
        result = self._post(f"/api/orders/{order.pk}/splits/{split_id}/pay", {
            "method": "cash",
            "reference": "cash-ref",
            "tip": "1.50",
        })
        assert result["status"] == 200
        assert result["data"]["paid"] is True

    def test_api_delete_split(self) -> None:
        order, item1, _ = self._create_order_with_items()
        splits = OrderService.split_by_items(order.pk, [
            {
                "label": "Juan",
                "items": [
                    {"order_item_id": str(item1.pk), "quantity": 2}
                ],
            },
        ])
        split_id = str(splits[0].pk)
        result = self._delete(f"/api/orders/{order.pk}/splits/{split_id}")
        assert result["status"] == 200
        assert not BillSplit.objects.filter(pk=split_id).exists()


class SetTableServiceTests(TestCase):
    def setUp(self) -> None:
        self.table1 = Table.objects.create(code="ST1", capacity=4)
        self.table2 = Table.objects.create(code="ST2", capacity=4)

    def test_set_table_assigns_and_marks_occupied(self) -> None:
        order = OrderService.create(table_id=None, notes="")
        updated = OrderService.set_table(order.pk, self.table1.pk)
        self.assertEqual(updated.table_id, self.table1.pk)
        self.table1.refresh_from_db()
        self.assertEqual(self.table1.status, Table.Status.OCCUPIED)

    def test_set_table_frees_previous_table(self) -> None:
        order = OrderService.create(table_id=self.table1.pk, notes="")
        OrderService.set_table(order.pk, self.table2.pk)
        self.table1.refresh_from_db()
        self.table2.refresh_from_db()
        self.assertEqual(self.table1.status, Table.Status.AVAILABLE)
        self.assertEqual(self.table2.status, Table.Status.OCCUPIED)

    def test_set_table_rejects_table_with_other_open_order(self) -> None:
        OrderService.create(table_id=self.table1.pk, notes="")
        order2 = OrderService.create(table_id=None, notes="")
        with self.assertRaises(ValueError):
            OrderService.set_table(order2.pk, self.table1.pk)

    def test_set_table_to_none_frees_table(self) -> None:
        order = OrderService.create(table_id=self.table1.pk, notes="")
        updated = OrderService.set_table(order.pk, None)
        self.assertIsNone(updated.table_id)
        self.table1.refresh_from_db()
        self.assertEqual(self.table1.status, Table.Status.AVAILABLE)


class PosFloorIntegrationViewTests(TestCase):
    def setUp(self) -> None:
        self.admin = User.objects.create_superuser(
            email="pos-floor-admin@test.com",
            password="admin1234",
            name="Admin",
        )
        self.client.force_login(self.admin)
        self.cat = Category.objects.create(name="Food")
        self.product = Product.objects.create(
            category=self.cat, name="Pizza", price=Decimal("10.00"),
        )
        self.table1 = Table.objects.create(code="PF1", capacity=4)
        self.table2 = Table.objects.create(code="PF2", capacity=2)

    def test_floor_status_without_layout(self) -> None:
        response = self.client.get(reverse("pos_floor_status"))
        assert response.status_code == 200
        data = response.json()
        assert data["layout"] is None
        assert data["items"] == []
        codes = {t["code"] for t in data["unplaced"]}
        assert {"PF1", "PF2"} <= codes

    def test_floor_status_lists_orders_without_table(self) -> None:
        order = OrderService.create(
            table_id=None, notes="", customer_name="Sin mesa"
        )
        OrderService.add_item(order.pk, self.product.pk, 1, "")
        OrderService.checkout(order.pk)

        response = self.client.get(reverse("pos_floor_status"))
        data = response.json()
        no_table = data["no_table_orders"]
        assert len(no_table) == 1
        assert no_table[0]["order_id"] == str(order.pk)
        assert no_table[0]["customer_name"] == "Sin mesa"
        assert no_table[0]["item_count"] == 1

    def test_floor_status_with_layout_and_open_order(self) -> None:
        layout = TableLayout.objects.create(name="Salón", width=400, height=300)
        TableLayoutItem.objects.create(
            layout=layout, table=self.table1, pos_x=10, pos_y=10
        )
        order = OrderService.create(table_id=self.table1.pk, notes="")

        response = self.client.get(reverse("pos_floor_status"))
        data = response.json()
        assert data["layout"] == {"width": 400, "height": 300}
        item = next(i for i in data["items"] if i["table_id"] == str(self.table1.pk))
        assert item["status"] == "occupied"
        assert item["order_id"] == str(order.pk)
        unplaced_codes = {t["code"] for t in data["unplaced"]}
        assert unplaced_codes == {"PF2"}

    def test_order_json_returns_items(self) -> None:
        order = OrderService.create(table_id=self.table1.pk, notes="")
        OrderService.add_item(order.pk, self.product.pk, 2, "")
        OrderService.checkout(order.pk)

        response = self.client.get(reverse("pos_order_json", args=[order.pk]))
        assert response.status_code == 200
        data = response.json()
        assert data["table_id"] == str(self.table1.pk)
        assert len(data["items"]) == 1
        assert data["items"][0]["quantity"] == 2

    def test_remove_item_updates_totals(self) -> None:
        order = OrderService.create(table_id=None, notes="")
        item = OrderService.add_item(order.pk, self.product.pk, 2, "")
        OrderService.checkout(order.pk)

        response = self.client.post(
            reverse("pos_remove_item", args=[order.pk, item.pk])
        )
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["subtotal"] == "0.00"

    def test_set_table_endpoint(self) -> None:
        order = OrderService.create(table_id=None, notes="")
        response = self.client.post(
            reverse("pos_set_table", args=[order.pk]),
            data=json.dumps({"table_id": str(self.table1.pk)}),
            content_type="application/json",
        )
        assert response.status_code == 200
        assert response.json()["table_id"] == str(self.table1.pk)
        self.table1.refresh_from_db()
        assert self.table1.status == Table.Status.OCCUPIED

    def test_set_table_endpoint_conflict(self) -> None:
        OrderService.create(table_id=self.table1.pk, notes="")
        order2 = OrderService.create(table_id=None, notes="")
        response = self.client.post(
            reverse("pos_set_table", args=[order2.pk]),
            data=json.dumps({"table_id": str(self.table1.pk)}),
            content_type="application/json",
        )
        assert response.status_code == 400
