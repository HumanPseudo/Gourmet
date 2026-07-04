from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from gourmet.apps.accounts.models import Role
from gourmet.apps.menu.models import Category, Product
from gourmet.apps.orders.models import DailyClose, Order, OrderItem, Payment
from gourmet.apps.orders.services import OrderService
from gourmet.apps.tables.models import Table

User = get_user_model()


class Command(BaseCommand):
    help = "Seed today's test data: orders, payments, kitchen items, daily close"

    def handle(self, *args, **options) -> None:
        for name in ("waiter", "kitchen", "admin"):
            Role.objects.get_or_create(name=name)

        admin, _ = User.objects.get_or_create(
            email="admin@example.com",
            defaults={"name": "Admin", "is_staff": True, "is_superuser": True},
        )
        if _:
            admin.set_password("admin")
            admin.save()

        tables_data = [
            ("Mesa 1", 2), ("Mesa 2", 4), ("Mesa 3", 4), ("Mesa 4", 6), ("Barra", 1),
        ]
        for code, capacity in tables_data:
            Table.objects.get_or_create(code=code, defaults={"capacity": capacity})

        cat_bebidas, _ = Category.objects.get_or_create(name="Bebidas", defaults={"sort_order": 1})
        cat_comidas, _ = Category.objects.get_or_create(name="Comidas", defaults={"sort_order": 2})

        products_data = [
            (cat_bebidas, "Coca Cola", 2.50, "IVA_19"),
            (cat_bebidas, "Agua Mineral", 1.50, "IVA_19"),
            (cat_bebidas, "Jugo Natural", 3.00, "EXENTO"),
            (cat_comidas, "Hamburguesa", 8.50, "INC_8"),
            (cat_comidas, "Pizza", 10.00, "INC_8"),
            (cat_comidas, "Ensalada", 6.50, "EXENTO"),
            (cat_comidas, "Papas Fritas", 4.00, "INC_8"),
        ]
        for cat, name, price, tax_type in products_data:
            Product.objects.get_or_create(
                name=name,
                defaults={"category": cat, "price": Decimal(str(price)), "tax_type": tax_type, "is_available": True},
            )

        self._create_today_data()

        self.stdout.write(self.style.SUCCESS("Today's seed data created"))

    def _create_today_data(self) -> None:
        tables = {t.code: t for t in Table.objects.filter(is_active=True)}
        prods = {p.name: p for p in Product.objects.filter(is_available=True)}
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        def make(table_code, notes, items, paid=False, customer_name=""):
            t = tables.get(table_code or "")
            order = OrderService.create(
                table_id=t.pk if t else None, notes=notes,
                customer_name=customer_name,
            )
            for name, qty in items:
                p = prods.get(name)
                if p:
                    OrderService.add_item(order.pk, p.pk, qty, "")
            order = OrderService.checkout(order.pk)
            if paid:
                OrderService.pay(order.pk, "cash", order.total, "")
                OrderService.close(order.pk)
            return order

        o1 = make("Mesa 1", "Sin cebolla", [("Hamburguesa", 2), ("Coca Cola", 2), ("Papas Fritas", 1)], paid=True, customer_name="Carlos")
        Order.objects.filter(pk=o1.pk).update(created_at=today_start + timedelta(hours=10))
        Order.objects.filter(pk=o1.pk).update(closed_at=today_start + timedelta(hours=11))

        o2 = make("Mesa 2", "", [("Pizza", 1), ("Agua Mineral", 2)], paid=True, customer_name="Ana")
        Order.objects.filter(pk=o2.pk).update(created_at=today_start + timedelta(hours=11))
        Order.objects.filter(pk=o2.pk).update(closed_at=today_start + timedelta(hours=11, minutes=45))

        o3 = make("Mesa 3", "Cumpleaños", [("Pizza", 3), ("Coca Cola", 4), ("Jugo Natural", 2)], paid=True, customer_name="Familia Pérez")
        Order.objects.filter(pk=o3.pk).update(created_at=today_start + timedelta(hours=12))
        Order.objects.filter(pk=o3.pk).update(closed_at=today_start + timedelta(hours=13, minutes=30))

        o4 = make("Mesa 4", "", [("Hamburguesa", 3), ("Papas Fritas", 2), ("Coca Cola", 3)], customer_name="Pedro")
        Order.objects.filter(pk=o4.pk).update(created_at=today_start + timedelta(hours=13))

        o5 = make("Barra", "Para llevar", [("Ensalada", 1), ("Jugo Natural", 1)], customer_name="Llevar")
        Order.objects.filter(pk=o5.pk).update(created_at=today_start + timedelta(hours=14))

        o6 = make(None, "Domicilio", [("Pizza", 2), ("Coca Cola", 2)])
        Order.objects.filter(pk=o6.pk).update(created_at=today_start + timedelta(hours=14, minutes=30))

        items_o4 = list(OrderItem.objects.filter(order=o4).order_by("created_at"))
        for i, item in enumerate(items_o4):
            item.status = ["preparing", "ready", "preparing"][i]
            item.save()
        OrderItem.objects.filter(order=o5).update(status="preparing")

        OrderService.pay(o4.pk, "card", Decimal("20.00"), "")

        DailyClose.objects.create(
            closed_by=User.objects.filter(is_superuser=True).first(),
            total_sales=sum(
                o.total for o in Order.objects.filter(status=Order.Status.CLOSED)
            ),
            total_cash=sum(
                p.amount for p in Payment.objects.filter(method="cash")
            ),
            cash_opening=Decimal("50000.00"),
            cash_counted=Decimal("150000.00"),
        )

        self.stdout.write(
            f"  Today: {Order.objects.count()} orders,"
            f" {OrderItem.objects.count()} items,"
            f" {Payment.objects.count()} payments,"
            f" {DailyClose.objects.count()} daily closes"
        )
