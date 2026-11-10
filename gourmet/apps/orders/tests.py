from __future__ import annotations

import json
import uuid
from decimal import Decimal

from django.http import Http404
from django.test import TestCase
from django.urls import reverse

from gourmet.apps.accounts.models import AuthToken, Role, User
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

    def test_split_by_percentage_sums_to_total(self) -> None:
        # Independent rounding of 33.33/33.33/33.34 of 37.80 overshoots by
        # 0.01; the last split must absorb the remainder.
        order, _, _ = self._create_order_with_items()
        splits = OrderService.split_by_percentage(order.pk, [
            {"label": "A", "percentage": Decimal("33.33")},
            {"label": "B", "percentage": Decimal("33.33")},
            {"label": "C", "percentage": Decimal("33.34")},
        ])
        assert sum(s.amount for s in splits) == order.total

    def test_split_order_recheckouts_original(self) -> None:
        # Move the pasta ($15 + 8%) to a new order; the original must drop it
        # and report the real moved count (not 0).
        order, _item1, item2 = self._create_order_with_items()
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("split_order", args=[order.pk]),
            data=json.dumps({"item_ids": [str(item2.pk)]}),
            content_type="application/json",
        )
        assert response.status_code == 200
        assert response.json()["moved"] == 1
        order.refresh_from_db()
        # Only the pizza (10*2) + 8% remains = 21.60
        assert order.total == Decimal("21.60")

    def test_pay_split_from_wrong_order_rejected(self) -> None:
        # A split may only be paid through its own order's endpoint.
        order, item1, _ = self._create_order_with_items()
        splits = OrderService.split_by_items(order.pk, [
            {
                "label": "Juan",
                "items": [{"order_item_id": str(item1.pk), "quantity": 2}],
            },
        ])
        other = Order.objects.create(table=self.table)
        result = self._post(
            f"/api/orders/{other.pk}/splits/{splits[0].pk}/pay",
            {"method": "cash"},
        )
        assert result["status"] == 404
        assert not BillSplit.objects.get(pk=splits[0].pk).paid


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


class FloorViewTests(TestCase):
    def setUp(self) -> None:
        self.admin = User.objects.create_superuser(
            email="floor-view-admin@test.com",
            password="admin1234",
            name="Admin",
        )
        self.client.force_login(self.admin)
        self.table1 = Table.objects.create(code="FV1", capacity=4)
        self.table2 = Table.objects.create(code="FV2", capacity=2)
        self.role = Role.objects.create(name="waiter")
        self.waiter = User.objects.create(
            email="waiter-fv@test.com", name="Ana", role=self.role, is_staff=True
        )

    def test_floor_view_renders(self) -> None:
        response = self.client.get(reverse("floor_view"))
        assert response.status_code == 200
        assert b"FV1" in response.content
        assert b"FV2" in response.content

    def test_floor_view_shows_order_link_for_occupied_table(self) -> None:
        order = OrderService.create(table_id=self.table1.pk, notes="")
        response = self.client.get(reverse("floor_view"))
        assert f"/pos/orders/{order.pk}/".encode() in response.content

    def test_assign_waiter_via_view(self) -> None:
        response = self.client.post(
            reverse("floor_view"),
            {"table_id": str(self.table1.pk), "waiter_id": str(self.waiter.pk)},
        )
        assert response.status_code == 302
        self.table1.refresh_from_db()
        assert self.table1.assigned_waiter_id == self.waiter.pk

    def test_unassign_waiter_via_view(self) -> None:
        self.table1.assigned_waiter = self.waiter
        self.table1.save()
        response = self.client.post(
            reverse("floor_view"),
            {"table_id": str(self.table1.pk), "waiter_id": ""},
        )
        assert response.status_code == 302
        self.table1.refresh_from_db()
        assert self.table1.assigned_waiter_id is None



class QROrderingTests(TestCase):
    """Flujo de autogestión: menú público, carrito y checkout por QR."""

    def setUp(self) -> None:
        self.admin = User.objects.create_superuser(
            email="qr-admin@test.com",
            password="admin1234",
            name="Admin",
        )
        self.role = Role.objects.create(name="waiter")
        self.waiter = User.objects.create(
            email="qr-waiter@test.com", name="Ana", role=self.role, is_staff=True
        )
        self.table = Table.objects.create(code="Q1", capacity=4)
        self.category = Category.objects.create(name="Food")
        self.product = Product.objects.create(
            category=self.category,
            name="Pizza",
            price=Decimal("10000.00"),
            is_available=True,
        )

    # ── Menú público ────────────────────────────────────────────────

    def test_menu_requires_known_table(self) -> None:
        assert self.client.get(
            reverse("menu_public", kwargs={"table_code": "NOPE"})
        ).status_code == 404

    def test_menu_renders_for_active_table(self) -> None:
        response = self.client.get(
            reverse("menu_public", kwargs={"table_code": "Q1"})
        )
        assert response.status_code == 200
        assert b"Pizza" in response.content

    def test_menu_404_for_inactive_table(self) -> None:
        self.table.is_active = False
        self.table.save()
        assert self.client.get(
            reverse("menu_public", kwargs={"table_code": "Q1"})
        ).status_code == 404

    # ── Carrito ─────────────────────────────────────────────────────

    def test_add_to_cart_stores_session(self) -> None:
        response = self.client.post(
            reverse("add_to_cart", kwargs={"table_code": "Q1"}),
            {"product_id": str(self.product.pk), "quantity": "2"},
        )
        assert response.status_code == 200
        assert b"Pizza" in response.content
        assert self.client.session["cart_Q1"] == {str(self.product.pk): 2}

    def test_add_to_cart_accumulates_quantity(self) -> None:
        for _ in range(2):
            self.client.post(
                reverse("add_to_cart", kwargs={"table_code": "Q1"}),
                {"product_id": str(self.product.pk), "quantity": "3"},
            )
        assert self.client.session["cart_Q1"] == {str(self.product.pk): 6}

    def test_add_to_cart_rejects_bad_uuid(self) -> None:
        response = self.client.post(
            reverse("add_to_cart", kwargs={"table_code": "Q1"}),
            {"product_id": "not-a-uuid", "quantity": "1"},
        )
        assert response.status_code == 400
        assert "cart_Q1" not in self.client.session

    def test_add_to_cart_rejects_non_numeric_quantity(self) -> None:
        response = self.client.post(
            reverse("add_to_cart", kwargs={"table_code": "Q1"}),
            {"product_id": str(self.product.pk), "quantity": "abc"},
        )
        assert response.status_code == 400
        assert "cart_Q1" not in self.client.session

    def test_add_to_cart_rejects_non_positive_quantity(self) -> None:
        response = self.client.post(
            reverse("add_to_cart", kwargs={"table_code": "Q1"}),
            {"product_id": str(self.product.pk), "quantity": "0"},
        )
        assert response.status_code == 400

    def test_add_to_cart_rejects_unavailable_product(self) -> None:
        self.product.is_available = False
        self.product.save()
        response = self.client.post(
            reverse("add_to_cart", kwargs={"table_code": "Q1"}),
            {"product_id": str(self.product.pk), "quantity": "1"},
        )
        assert response.status_code == 400

    def test_add_to_cart_rejects_unknown_table(self) -> None:
        response = self.client.post(
            reverse("add_to_cart", kwargs={"table_code": "NOPE"}),
            {"product_id": str(self.product.pk), "quantity": "1"},
        )
        assert response.status_code == 404

    def test_remove_from_cart_drops_item(self) -> None:
        self.client.post(
            reverse("add_to_cart", kwargs={"table_code": "Q1"}),
            {"product_id": str(self.product.pk), "quantity": "2"},
        )
        response = self.client.post(
            reverse("remove_from_cart", kwargs={"table_code": "Q1"}),
            {"product_id": str(self.product.pk)},
        )
        assert response.status_code == 200
        assert self.client.session["cart_Q1"] == {}

    def test_remove_from_cart_rejects_bad_uuid(self) -> None:
        response = self.client.post(
            reverse("remove_from_cart", kwargs={"table_code": "Q1"}),
            {"product_id": "nope"},
        )
        assert response.status_code == 400

    # ── Checkout ────────────────────────────────────────────────────

    def test_checkout_creates_qr_order_with_items(self) -> None:
        self.client.post(
            reverse("add_to_cart", kwargs={"table_code": "Q1"}),
            {"product_id": str(self.product.pk), "quantity": "2"},
        )
        response = self.client.post(
            reverse("checkout_qr", kwargs={"table_code": "Q1"})
        )
        assert response.status_code == 200
        order = Order.objects.get()
        assert order.source == Order.Source.QR
        assert order.table_id == self.table.pk
        item = order.items.get()
        assert item.quantity == 2
        assert not self.client.session.get("cart_Q1")

    def test_checkout_empties_cart(self) -> None:
        self.client.post(
            reverse("add_to_cart", kwargs={"table_code": "Q1"}),
            {"product_id": str(self.product.pk), "quantity": "1"},
        )
        self.client.post(reverse("checkout_qr", kwargs={"table_code": "Q1"}))
        assert not self.client.session.get("cart_Q1")

    def test_checkout_marks_table_occupied(self) -> None:
        self.client.post(
            reverse("add_to_cart", kwargs={"table_code": "Q1"}),
            {"product_id": str(self.product.pk), "quantity": "1"},
        )
        self.client.post(reverse("checkout_qr", kwargs={"table_code": "Q1"}))
        self.table.refresh_from_db()
        assert self.table.status == Table.Status.OCCUPIED

    def test_checkout_reuses_open_qr_order(self) -> None:
        for _ in range(2):
            self.client.post(
                reverse("add_to_cart", kwargs={"table_code": "Q1"}),
                {"product_id": str(self.product.pk), "quantity": "1"},
            )
            self.client.post(reverse("checkout_qr", kwargs={"table_code": "Q1"}))
        assert Order.objects.filter(source=Order.Source.QR).count() == 1
        assert Order.objects.get().items.count() == 2

    def test_checkout_without_cart_redirects(self) -> None:
        response = self.client.post(
            reverse("checkout_qr", kwargs={"table_code": "Q1"})
        )
        assert response.status_code == 302
        assert not Order.objects.exists()

    def test_checkout_requires_post(self) -> None:
        response = self.client.get(
            reverse("checkout_qr", kwargs={"table_code": "Q1"})
        )
        assert response.status_code == 405

    # ── QRs para el personal ────────────────────────────────────────

    def test_generate_qr_returns_png(self) -> None:
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("generate_qr_table", kwargs={"table_code": "Q1"})
        )
        assert response.status_code == 200
        assert response["Content-Type"] == "image/png"
        assert response.content.startswith(b"\x89PNG")

    def test_generate_qr_requires_login(self) -> None:
        response = self.client.get(
            reverse("generate_qr_table", kwargs={"table_code": "Q1"})
        )
        assert response.status_code == 302

    def test_print_qr_tables_lists_table(self) -> None:
        self.client.force_login(self.admin)
        response = self.client.get(reverse("print_qr_tables"))
        assert response.status_code == 200
        assert b"Q1" in response.content


class SplitEqualAPITests(TestCase):
    """Regresiones del endpoint de división de cuentas."""

    def setUp(self) -> None:
        self.admin = User.objects.create_superuser(
            email="split-equal-admin@test.com",
            password="admin1234",
            name="Admin",
        )
        self.token = AuthToken.create_token(self.admin)
        self.cat = Category.objects.create(name="Food")
        self.product = Product.objects.create(
            category=self.cat, name="Pizza", price=Decimal("30000.00"),
        )
        self.table = Table.objects.create(code="SE1", capacity=4)
        self.order = OrderService.create(table_id=self.table.pk, notes="")
        self.item = OrderService.add_item(self.order.pk, self.product.pk, 3, "")
        OrderService.checkout(self.order.pk)

    def _post(self, payload: dict) -> dict:
        response = self.client.post(
            f"/api/orders/{self.order.pk}/splits",
            data=json.dumps(payload),
            content_type="application/json",
            headers={"authorization": f"Bearer {self.token.key}"},
        )
        assert response.status_code == 201, response.content
        return response.json()

    def test_equal_split_without_explicit_method(self) -> None:
        """El método 'equal' debe venir por defecto en el payload."""
        splits = self._post({"n_splits": 3, "labels": ["A", "B", "C"]})
        assert len(splits) == 3
        assert {s["method"] for s in splits} == {"equal"}

    def test_equal_split_amounts_sum_to_total(self) -> None:
        splits = self._post({"n_splits": 3, "labels": ["A", "B", "C"]})
        total = sum(Decimal(s["amount"]) for s in splits)
        self.order.refresh_from_db()
        assert total == self.order.total

    def test_list_splits_returns_split_shape(self) -> None:
        self._post({"n_splits": 2, "labels": ["A", "B"]})
        response = self.client.get(
            f"/api/orders/{self.order.pk}/splits",
            headers={"authorization": f"Bearer {self.token.key}"},
        )
        assert response.status_code == 200
        splits = response.json()
        assert len(splits) == 2
        for split in splits:
            assert set(split) >= {
                "id", "order_id", "label", "method", "amount", "items"
            }
            assert isinstance(split["items"], list)

    def test_by_percentage_still_routes_correctly(self) -> None:
        splits = self._post(
            {
                "method": "by_percentage",
                "splits": [
                    {"label": "A", "percentage": "60"},
                    {"label": "B", "percentage": "40"},
                ],
            }
        )
        assert {s["method"] for s in splits} == {"by_percentage"}

    def test_unknown_method_returns_400(self) -> None:
        response = self.client.post(
            f"/api/orders/{self.order.pk}/splits",
            data=json.dumps(
                {"method": "bogus", "splits": [{"label": "A", "items": []}]}
            ),
            content_type="application/json",
            headers={"authorization": f"Bearer {self.token.key}"},
        )
        assert response.status_code == 400


class OrderSourceTests(TestCase):
    def setUp(self) -> None:
        self.cat = Category.objects.create(name="Food")
        self.product = Product.objects.create(
            category=self.cat, name="Pizza", price=Decimal("10000.00"),
        )

    def test_create_defaults_to_pos_source(self) -> None:
        order = OrderService.create(table_id=None, notes="")
        assert order.source == Order.Source.POS

    def test_create_accepts_qr_source(self) -> None:
        order = OrderService.create(
            table_id=None, notes="", source=Order.Source.QR
        )
        assert order.source == Order.Source.QR

    def test_create_marks_table_occupied(self) -> None:
        table = Table.objects.create(code="SRC1", capacity=4)
        OrderService.create(table_id=table.pk, notes="")
        table.refresh_from_db()
        assert table.status == Table.Status.OCCUPIED

    def test_create_from_items_is_atomic(self) -> None:
        table = Table.objects.create(code="SRC2", capacity=4)
        missing = uuid.uuid4()
        with self.assertRaises(Http404):
            OrderService.create_from_items(
                table.pk, [(self.product.pk, 1), (missing, 1)]
            )
        assert not Order.objects.exists()

    def test_create_from_items_reuses_open_order(self) -> None:
        table = Table.objects.create(code="SRC3", capacity=4)
        OrderService.create_from_items(table.pk, [(self.product.pk, 1)])
        OrderService.create_from_items(table.pk, [(self.product.pk, 2)])
        assert Order.objects.count() == 1
        assert Order.objects.get().items.count() == 2
