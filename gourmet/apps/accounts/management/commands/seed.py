from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandParser
from django.utils import timezone

from gourmet.apps.accounts.models import Role
from gourmet.apps.menu.models import Category, Product
from gourmet.apps.orders.models import Order, OrderItem, Payment
from gourmet.apps.orders.services import OrderService
from gourmet.apps.reservations.models import Reservation
from gourmet.apps.tables.models import Table, TableLayout, TableLayoutItem

User = get_user_model()


class Command(BaseCommand):
    help = "Seed initial data: roles, users, tables, menu items"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--demo", action="store_true",
            help="Create sample orders, payments, and kitchen items",
        )

    def handle(self, *args, **options) -> None:
        roles = {}
        for name in ("waiter", "kitchen", "admin"):
            role, created = Role.objects.get_or_create(name=name)
            roles[name] = role
            self.stdout.write(f"  {'Created' if created else 'Exists'} role: {name}")

        users_data = [
            ("waiter@example.com", "waiter1", "Mesero Uno", "waiter"),
            ("kitchen@example.com", "kitchen1", "Cocinero Uno", "kitchen"),
            ("admin@example.com", "admin", "Admin", "admin"),
        ]
        for email, password, name, role_name in users_data:
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "name": name,
                    "role": roles.get(role_name),
                    "is_staff": True,
                },
            )
            if created:
                user.set_password(password)
                user.save()
                self.stdout.write(f"  Created user: {email} / {password}")
            else:
                self.stdout.write(f"  Exists user: {email}")

        tables_data = [
            ("Mesa 1", 2),
            ("Mesa 2", 4),
            ("Mesa 3", 4),
            ("Mesa 4", 6),
            ("Barra", 1),
        ]
        tables = {}
        for code, capacity in tables_data:
            table, created = Table.objects.get_or_create(
                code=code, defaults={"capacity": capacity}
            )
            tables[code] = table
            self.stdout.write(f"  {'Created' if created else 'Exists'} table: {code}")

        layout, created = TableLayout.objects.get_or_create(
            name="Salón Principal", defaults={"width": 640, "height": 420}
        )
        verb = "Created" if created else "Exists"
        self.stdout.write(f"  {verb} layout: {layout.name}")

        # Mesa 4 and Barra are left unplaced so the palette (drag-in) is exercised too.
        layout_items = [
            ("Mesa 1", 60, 60, "square", 0),
            ("Mesa 2", 260, 60, "round", 0),
            ("Mesa 3", 60, 240, "square", 90),
        ]
        for code, x, y, shape, rotation in layout_items:
            _, created = TableLayoutItem.objects.update_or_create(
                layout=layout, table=tables[code],
                defaults={
                    "pos_x": x, "pos_y": y, "shape": shape, "rotation": rotation
                },
            )
            verb = "Placed" if created else "Updated"
            self.stdout.write(f"  {verb} {code} on layout")

        today = timezone.localdate()
        reservations_data = [
            ("Laura Gómez", "3011112222", 4, today, "20:00", "Mesa 2", ""),
            ("Andrés Ruiz", "3013334444", 2, today, "20:30", None, "Alérgico a maní"),
            (
                "Sofía Castro", "3015556666", 6, today + timedelta(days=1), "19:30",
                "Mesa 4", "Cumpleaños",
            ),
        ]
        for name, phone, size, day, hour, table_code, notes in reservations_data:
            reserved_for = timezone.make_aware(
                datetime.combine(day, datetime.strptime(hour, "%H:%M").time())
            )
            _, created = Reservation.objects.get_or_create(
                customer_name=name,
                reserved_for=reserved_for,
                defaults={
                    "customer_phone": phone,
                    "party_size": size,
                    "table": tables.get(table_code) if table_code else None,
                    "notes": notes,
                },
            )
            verb = "Created" if created else "Exists"
            self.stdout.write(f"  {verb} reservation: {name} @ {hour}")

        cat_bebidas, _ = Category.objects.get_or_create(
            name="Bebidas", defaults={"sort_order": 1}
        )
        if _:
            self.stdout.write(f"  Created category: {cat_bebidas.name}")

        cat_comidas, _ = Category.objects.get_or_create(
            name="Comidas", defaults={"sort_order": 2}
        )
        if _:
            self.stdout.write(f"  Created category: {cat_comidas.name}")

        products_data = [
            (cat_bebidas, "Coca Cola", 2.50, "IVA_19"),
            (cat_bebidas, "Agua Mineral", 1.50, "IVA_19"),
            (cat_bebidas, "Jugo Natural", 3.00, "EXENTO"),
            (cat_comidas, "Hamburguesa", 8.50, "INC_8"),
            (cat_comidas, "Pizza", 10.00, "INC_8"),
            (cat_comidas, "Ensalada", 6.50, "EXENTO"),
            (cat_comidas, "Papas Fritas", 4.00, "INC_8"),
        ]

        for category, name, price, tax_type in products_data:
            obj, created = Product.objects.get_or_create(
                name=name,
                defaults={
                    "category": category,
                    "price": Decimal(str(price)),
                    "tax_type": tax_type,
                    "is_available": True,
                },
            )
            if not created:
                changed = []
                if obj.tax_type != tax_type:
                    obj.tax_type = tax_type
                    changed.append(f"tax_type→{tax_type}")
                if obj.price != Decimal(str(price)):
                    obj.price = Decimal(str(price))
                    changed.append(f"price→${price}")
                if changed:
                    obj.save()
                    self.stdout.write(
                        f"  Updated product: {name} ({', '.join(changed)})"
                    )
                else:
                    self.stdout.write(
                        f"  Exists product: {name} (${price}, {tax_type})"
                    )
            else:
                self.stdout.write(
                    f"  Created product: {name} (${price}, {tax_type})"
                )

        if options["demo"]:
            self._create_demo_data()

        self.stdout.write(self.style.SUCCESS("Seed complete"))

    def _create_demo_data(self) -> None:
        Order.objects.all().delete()
        OrderItem.objects.all().delete()
        Payment.objects.all().delete()

        tables = {t.code: t for t in Table.objects.filter(is_active=True)}
        prods = {p.name: p for p in Product.objects.filter(is_available=True)}

        def make(
            table_code: str | None, notes: str, items: list,
            paid: bool = False,
        ) -> Order:
            t = tables.get(table_code or "")
            order = OrderService.create(
                table_id=t.pk if t else None, notes=notes,
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

        now = timezone.now()

        o1 = make(
            "Mesa 1", "Sin cebolla",
            [("Hamburguesa", 2), ("Coca Cola", 2), ("Papas Fritas", 1)],
            paid=True,
        )
        Order.objects.filter(pk=o1.pk).update(created_at=now - timedelta(hours=3))
        o2 = make("Mesa 2", "", [("Pizza", 1), ("Agua Mineral", 2)], paid=True)
        Order.objects.filter(pk=o2.pk).update(created_at=now - timedelta(hours=2))
        o3 = make(
            "Mesa 3", "Cumpleaños",
            [("Pizza", 3), ("Coca Cola", 4), ("Jugo Natural", 2)],
            paid=True,
        )
        Order.objects.filter(pk=o3.pk).update(
            created_at=now - timedelta(hours=1, minutes=30),
        )

        o4 = make(
            "Mesa 4", "",
            [("Hamburguesa", 3), ("Papas Fritas", 2), ("Coca Cola", 3)],
        )
        Order.objects.filter(pk=o4.pk).update(created_at=now - timedelta(minutes=45))
        o5 = make("Barra", "Para llevar", [("Ensalada", 1), ("Jugo Natural", 1)])
        Order.objects.filter(pk=o5.pk).update(created_at=now - timedelta(minutes=15))
        o6 = make(None, "Domicilio", [("Pizza", 2), ("Coca Cola", 2)])
        Order.objects.filter(pk=o6.pk).update(created_at=now - timedelta(minutes=5))

        items_m4 = list(OrderItem.objects.filter(order=o4).order_by("created_at"))
        for i, item in enumerate(items_m4):
            item.status = ["preparing", "ready", "preparing"][i]
            item.save()
        OrderItem.objects.filter(order=o5).update(status="preparing")

        OrderService.pay(o4.pk, "card", Decimal("20.00"), "")

        self.stdout.write(
            f"  Demo: {Order.objects.count()} orders,"
            f" {OrderItem.objects.count()} items,"
            f" {Payment.objects.count()} payments"
        )
