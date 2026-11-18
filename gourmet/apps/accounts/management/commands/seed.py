from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandParser
from django.utils import timezone

from gourmet.apps.accounts.models import Role
from gourmet.apps.menu.models import Category, Product, ProductTag
from gourmet.apps.orders.models import Order, OrderItem, Payment
from gourmet.apps.orders.services import OrderService
from gourmet.apps.reservations.models import Reservation
from gourmet.apps.tables.models import Table, TableLayout, TableLayoutItem

User = get_user_model()


class Command(BaseCommand):
    help = "Seed initial data: roles, users, tables, menu items"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--demo",
            action="store_true",
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
            ("admin@example.com", "admin", "Administrador", "admin"),
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
                layout=layout,
                table=tables[code],
                defaults={"pos_x": x, "pos_y": y, "shape": shape, "rotation": rotation},
            )
            verb = "Placed" if created else "Updated"
            self.stdout.write(f"  {verb} {code} on layout")

        today = timezone.localdate()
        reservations_data = [
            ("Laura Gómez", "3011112222", 4, today, "20:00", "Mesa 2", ""),
            ("Andrés Ruiz", "3013334444", 2, today, "20:30", None, "Alérgico a maní"),
            (
                "Sofía Castro",
                "3015556666",
                6,
                today + timedelta(days=1),
                "19:30",
                "Mesa 4",
                "Cumpleaños",
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
        cat_comidas, _ = Category.objects.get_or_create(
            name="Comidas", defaults={"sort_order": 2}
        )
        cat_postres, _ = Category.objects.get_or_create(
            name="Postres", defaults={"sort_order": 3}
        )

        products_data = [
            (cat_bebidas, "Agua Mineral", 2500, "IVA_19"),
            (cat_bebidas, "Jugo de Lulo", 4000, "EXENTO"),
            (cat_bebidas, "Limonada", 3500, "EXENTO"),
            (cat_comidas, "Hamburguesa", 8500, "INC_8"),
            (cat_comidas, "Pizza", 10000, "INC_8"),
            (cat_comidas, "Bandeja Paisa", 18000, "INC_8"),
            (cat_comidas, "Arepa con Queso", 3000, "EXENTO"),
            (cat_comidas, "Empanadas", 2000, "INC_8"),
            (cat_postres, "Postre de Tres Leches", 5000, "IVA_19"),
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
                self.stdout.write(f"  Created product: {name} (${price}, {tax_type})")

        if options["demo"]:
            self._create_demo_data()

        self.stdout.write(self.style.SUCCESS("Seed complete"))

        badges_data = [
            {
                "name": "Vegetariano",
                "slug": "vegetariano",
                "description": "Apto para dieta vegetariana",
                "color": "#55a045",
                "sort_order": 1,
                "svg": (
                    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 368 368">'
                    '<path fill="#55a045" d="M257.5 34.7c-8.8 23.7-17 37.5-31.3 52.5'
                    "-18.9 19.8-35.8 30.4-71.3 44.6-32.1 12.8-48 21.2-64.4 34-29.9 23"
                    "-47.1 55.7-49 93l-.4 9.7 1.4-6c9.7-39.7 25-62.9 54.3-82.2 16.5"
                    "-10.9 31.2-16.8 77.7-31.3 22.3-7 43.7-18 60.9-31.4 10.3-8 26.7"
                    "-25.2 33.1-34.5l4.9-7.2 4.4 6.8c8.6 13.2 15 28.9 18.8 46.4 1.5"
                    " 6.7 1.9 12.5 1.9 29.4-.1 18.9-.4 22.3-2.8 33.7-5.1 24.1-14.8"
                    " 46.4-27.3 63.1-17.3 23-42.7 35.8-82.6 41.7-13.9 2.1-94.3 5.9"
                    "-95.6 4.5-1.1-1.1 20.6-21.6 31.3-29.6 5.5-4.1 16.2-11.5 23.8"
                    "-16.4 53-34.6 59.8-39.6 77.3-57 20.4-20.4 33.9-42.9 36.9-62 .6"
                    "-3.4.1-2.8-3.5 4.5-6.4 12.9-12.5 21.5-23.5 32.9-18.7 19.3-33.1"
                    " 28.7-87 56.6-30.1 15.6-42.9 23.5-60.5 37.6-13.1 10.4-25.4 23.7"
                    "-33.3 36.2-5 7.7-19 34.8-18.3 35.4.3.3 5.8-.2 12.3-1.1s15.4-2.1"
                    " 19.8-2.7 33.6-1.5 65-1.9c58.8-.8 63.7-1.1 84.5-5.7 18.5-4 39"
                    "-12.5 53.6-22.3 10.6-7.1 27.5-24.3 35.1-35.6 11.5-17.4 22.4-44"
                    " 27.2-66.5 6.8-31.8 6.1-63.2-1.8-90.8-8.2-28.3-20.2-48.7-41.3"
                    '-69.9-8.9-9-23.3-21.2-25-21.2-.3 0-2.7 5.7-5.3 12.7"/>'
                    "</svg>"
                ),
            },
            {
                "name": "Picante",
                "slug": "picante",
                "description": "Contiene ingredientes picantes",
                "color": "#FE0000",
                "sort_order": 2,
                "svg": (
                    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 368 368">'
                    '<g transform="translate(0, 11.04) scale(2.4533)">'
                    '<path fill="#FE0000" d="M103.4 28.9c-3.1 3-5.4 8.8-5.4 13.4 0'
                    " 2.2-.5 2.6-4.4 3.1-5.7.9-12.7 5.4-15.6 10-1.8 2.9-2.4 5.9-3"
                    " 13.9-.4 5.6-1.4 11.8-2.2 13.8-3.6 8.4-12.3 14.8-20.1 14.9-8.6"
                    " 0-10.5 5.3-4 11 5.4 4.8 9.8 6.2 20.3 6.7 22.6 1.1 40.8-8.7"
                    " 49.4-26.6 4.9-10.2 6.3-19.1 4.3-26.2-2-6.9-7.3-13.1-13.2-15.5"
                    "-2.4-1.1-4.7-2.5-5-3.3-.9-2.2 1.4-8.8 4-11.9 2.9-3.5 3.1-4.8"
                    '.9-5.6-2.4-.9-2.8-.8-6 2.3"/>'
                    "</g></svg>"
                ),
            },
            {
                "name": "Nuevo",
                "slug": "nuevo",
                "description": "Producto recién agregado al menú",
                "color": "#172F3B",
                "sort_order": 3,
                "svg": (
                    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 368 368">'
                    '<g transform="scale(1.415385)" fill="#172F3B">'
                    '<path d="M106 16.5c-1.4.7-4.6 3.8-7 6.9s-5 5.8-5.7 6.1c-.7.2'
                    "-3.6 0-6.4-.5-13.4-2.6-18-.7-21.4 8.6C61 49.6 62 48.7 53.8 50"
                    " 40.1 52.3 38 54.6 38 67c0 4.7-.4 9-.8 9.6-.4.5-3.5 2.7-6.9 4.8"
                    "-11 6.6-12.4 10.7-7.8 23.1 2.9 7.5 3.2 6.3-4.3 15.8-2.4 3-4.5"
                    " 7-4.8 8.9-.6 3.4.9 6.1 9 16.2l2.8 3.6-2.6 7.1c-4.6 12.3-3.3"
                    " 16.6 6.2 22 9.2 5.1 9.2 5.1 9.2 14.3 0 6.3.5 8.8 2 11.3 2.4"
                    " 3.9 3.8 4.7 12 6.2 3.6.7 7.3 1.4 8.2 1.7 1 .3 2.8 3.5 4.4 7.7"
                    " 3 8 6.4 12.3 10.3 13.2 1.4.3 6.2-.1 10.5-.9l7.9-1.4 7.2 7.4c6.4"
                    " 6.7 7.5 7.4 10.9 7.4 2.7 0 6-1.2 10.8-4 3.9-2.2 7.4-4 7.9-4 .6"
                    " 0 4.3 1.8 8.3 4 11 6 14.9 5.3 22.6-4.4 2.4-3.1 5-5.8 5.7-6.1"
                    ".7-.2 3.6 0 6.4.5 7.8 1.5 14.1 1.2 16.7-.8 1.2-.9 3.7-5.5 5.5"
                    "-10.2l3.3-8.5 8-1.6c13.8-2.7 15.4-4.5 15.4-16.9 0-4.7.4-9 .8"
                    "-9.6.4-.5 3.5-2.7 6.9-4.8 11-6.6 12.4-10.7 7.8-23.1-2.9-7.5-3.2"
                    "-6.3 4.3-15.8 2.4-3 4.5-7 4.8-8.9.6-3.4-.9-6.1-9-16.2l-2.8-3.6"
                    " 2.6-7.1c4.6-12.3 3.3-16.6-6.2-22-9.2-5.1-9.2-5.1-9.2-14.3 0"
                    "-6.3-.5-8.8-2-11.3-2.4-3.9-3.8-4.7-12-6.2-3.6-.7-7.3-1.4-8.2"
                    "-1.7-1-.3-2.8-3.5-4.4-7.7-3-8-6.4-12.3-10.3-13.2-1.4-.3-6.2.1"
                    "-10.5.9l-7.9 1.4-7.2-7.4c-6.4-6.7-7.5-7.4-10.9-7.4-2.7 0-6 1.2"
                    "-10.8 4-3.9 2.2-7.4 4-7.9 4-.6 0-4.3-1.8-8.3-4-7.6-4.2-11.4-4.8"
                    "-15.6-2.5M119.7 27c4.2 2.2 8.7 4 10.1 4 1.3 0 5.7-1.8 9.7-4s7.9"
                    "-4 8.8-4c.8 0 4 2.9 7.2 6.5 6.9 7.9 9.1 8.6 19.9 6.8 5.5-1 8.2"
                    "-1.1 8.9-.4.6.6 2.5 4.6 4.2 8.8 1.8 4.5 4 8.4 5.5 9.5 1.4 1 6"
                    " 2.5 10.3 3.3 4.4.8 8.3 1.8 8.8 2.1s.9 4.3.9 9c0 5.3.5 9.5 1.4"
                    " 11.2.8 1.5 4.7 4.6 9 7.2 8.7 5.2 8.8 5.5 5 15.6-3.3 8.8-2.8"
                    " 10.9 4.1 19.5 3 3.7 5.5 7.2 5.5 7.8 0 .5-2.3 3.7-5.1 7-7.1 8.5"
                    "-7.5 10.6-4 20.7 1.7 5.1 2.5 8.8 2 9.7-.5.8-4 3.3-7.9 5.6-3.8"
                    " 2.3-7.5 5.2-8.2 6.4s-1.5 6.5-1.8 11.7l-.5 9.4-8.3 1.7c-4.6.9"
                    "-9.5 2.5-10.9 3.5-1.6 1.2-3.7 4.9-5.4 9.4-1.6 4.1-3.4 8-4.1 8.6"
                    "-1 1-3.1.9-9.5-.2-10.5-1.9-13.1-.9-19.8 7.5-2.8 3.3-5.6 6.1-6.4"
                    " 6.1s-4.7-1.8-8.7-4-8.5-4-10-4-5.9 1.8-9.9 4-7.9 4-8.6 4c-.8 0"
                    "-4.1-2.9-7.4-6.5-3.6-3.9-7.2-6.9-9-7.4s-6.1-.2-10.9.6c-5.4.9"
                    "-8.3 1-9 .3-.5-.5-2.4-4.5-4.1-8.7-1.8-4.5-4-8.4-5.5-9.5-1.4-1"
                    "-6-2.5-10.3-3.3-4.4-.8-8.3-1.8-8.8-2.1s-.9-4.3-.9-9c0-5.3-.5"
                    "-9.5-1.4-11.2-.8-1.5-4.7-4.6-9-7.2-5.2-3.1-7.6-5.1-7.6-6.4 0"
                    "-1.1 1.2-5.3 2.6-9.4 1.6-4.8 2.3-8.4 1.9-10.1-.4-1.4-3.1-5.6"
                    "-6.1-9.3s-5.4-7.1-5.4-7.7c0-.5 2.3-3.7 5.1-7 7.1-8.5 7.5-10.6"
                    " 4-20.7-1.7-5.1-2.5-8.8-2-9.7.5-.8 4-3.3 7.9-5.6 3.8-2.3 7.5"
                    "-5.2 8.2-6.4S45.7 74.2 46 69l.5-9.4 8.3-1.7C65.7 55.7 67.9 54"
                    " 71.2 45c3.8-10.2 3.7-10.1 13.5-8.4 10.5 1.8 13 .9 19.8-7.4 2.8"
                    '-3.4 5.6-6.1 6.3-6.1.8-.1 4.8 1.7 8.9 3.9"/>'
                    '<path d="M106.4 42.5c-3.4 3.6-6.8 6.5-7.5 6.5s-4.1-.5-7.7-1.1c'
                    "-8.8-1.6-10.3-.7-13.3 7.5-1.2 3.7-3 7.2-3.8 8-.9.7-4.5 1.9-8.1"
                    " 2.5-8.9 1.7-10 2.9-10 11 0 3.6-.6 7.7-1.3 9-.6 1.4-3.9 4.1-7.1"
                    " 6.1-7.9 4.8-8.4 6.1-5.2 14.9 2.9 8.1 2.9 8.2-3.6 16.4-2.1 2.7"
                    "-3.8 5.9-3.8 7.1s1.8 4.4 4.1 7.1c6.4 7.7 6.4 7.7 3.3 16.1-2.5"
                    " 6.8-2.5 7.5-1.1 9.8.9 1.3 4.1 3.7 7.1 5.5 3 1.7 6 3.9 6.6 5 .5"
                    " 1.1 1 5.1 1 8.9 0 8.5 1 9.6 10.3 11.6 3.7.7 7.3 1.9 8 2.5.8.6"
                    " 2.6 4.2 4.1 8.1 2.2 5.4 3.3 7.1 5.2 7.6 2.3.6 8.9 0 14.2-1.3"
                    " 1.9-.4 3.5.7 8.7 6.2 7.3 7.6 7.7 7.7 16.5 2.5 2.8-1.7 6-3 7.1"
                    "-3 1.2 0 5 1.6 8.5 3.6 4.2 2.4 7 3.3 8.4 2.9 1.1-.3 4.1-3.1 6.6"
                    "-6 2.6-3 5.4-5.7 6.2-6 .9-.3 4.8-.1 8.7.6 9.3 1.5 10.6.8 13.6"
                    "-7.6 1.2-3.6 3-7.1 3.8-7.9.9-.7 4.5-1.9 8.1-2.5 8.9-1.7 10-2.9"
                    " 10-11 0-3.6.6-7.7 1.3-9 .6-1.4 3.9-4.1 7.1-6.1 7.9-4.8 8.4-6.1"
                    " 5.2-14.9-2.9-8.1-2.9-8.2 3.6-16.4 2.1-2.7 3.8-5.9 3.8-7.1s-1.8"
                    "-4.4-4.1-7.1c-6.4-7.7-6.4-7.7-3.3-16.1 2.5-6.8 2.5-7.5 1.1-9.8"
                    "-.9-1.3-4.1-3.7-7.1-5.5-3-1.7-6-3.9-6.6-5-.5-1.1-1-5.1-1-8.9 0"
                    "-8.5-1-9.6-10.3-11.6-3.7-.7-7.3-1.9-8-2.5-.8-.6-2.6-4.2-4.1-8.1"
                    "-2.2-5.4-3.3-7.1-5.2-7.6-2.3-.6-8.9 0-14.2 1.3-1.9.4-3.5-.7"
                    "-8.7-6.2-7.3-7.6-7.7-7.7-16.5-2.5-2.8 1.7-6 3-7.1 3-1.2 0-4.9"
                    "-1.6-8.3-3.5-3.5-1.9-6.9-3.5-7.6-3.5-.8 0-4.2 2.9-7.6 6.5m88.3"
                    " 72c12.5 2.5 13.6 26 1.4 30.7-4.1 1.5-11.8 1.1-15.2-.9-8.8-5.1"
                    "-9.2-22.9-.6-28.3 2.6-1.6 7.6-2.9 9.7-2.5.8.2 2.9.6 4.7 1m-126.8"
                    " 9 5.6 9 .3-9.3.3-9.2H81v32h-3.7c-3.7 0-3.9-.2-9.3-9.1l-5.5-9.1"
                    "-.3 9.1-.3 9.1H55v-32.1l3.7.3c3.4.3 4 .9 9.2 9.3m25.9 2.4c.1"
                    " 6.4.8 12.1 1.4 12.8s2.2 1.3 3.7 1.3c5.2 0 5.6-1 5.9-14l.4-12h6.8"
                    "v11.5c0 16.3-1.8 20-10 20.5-6.7.5-9 0-12.2-2.9l-3.3-2.9-.4-13.2"
                    "-.3-13.1 3.8.3 3.9.3zM141 117v3h-16v6h15v6h-15v8h17v6.1l-12.2-.3"
                    "-12.3-.3-.3-14.5c-.1-7.9 0-15 .2-15.7.4-1 3.5-1.3 12.1-1.3H141zm13"
                    " 6.7c1.8 5.4 3.6 10.1 3.9 10.6.4.4 2.2-4 4.1-9.8l3.4-10.5h3.9c2.9"
                    " 0 3.8.3 3.4 1.4-.3.8-2.9 8-5.8 16l-5.2 14.6h-7.5l-5.3-15.2c-3"
                    '-8.3-5.5-15.5-5.7-16-.2-.4 1.4-.8 3.6-.8h4z"/>'
                    '<path d="M184.8 121c-2.3 1.4-4.1 7.5-3.4 11.3 1.5 7.4 9.4 10.3'
                    ' 13.5 5.1 3.1-3.9 2.9-12.3-.2-15.2-2.5-2.3-7-2.8-9.9-1.2"/>'
                    "</g></svg>"
                ),
            },
        ]

        for badge_data in badges_data:
            tag, created = ProductTag.objects.get_or_create(
                slug=badge_data["slug"],
                defaults={
                    "name": badge_data["name"],
                    "description": badge_data["description"],
                    "color": badge_data["color"],
                    "sort_order": badge_data["sort_order"],
                },
            )
            # Solo guardar si el badge es nuevo o si realmente no tiene archivo
            if created or not tag.icon.name:
                svg_bytes = str(badge_data["svg"]).encode("utf-8")
                tag.icon.save(
                    f"{badge_data['slug']}.svg",
                    ContentFile(svg_bytes),
                    save=True,
                )
                verb = "Created" if created else "Updated"
                self.stdout.write(f"  {verb} badge: {badge_data['name']}")
            else:
                self.stdout.write(f"  Exists badge: {badge_data['name']}")

        # Hamburguesa -> Picante (si se desea ejemplo)
        try:
            hamburguesa = Product.objects.get(name="Hamburguesa")
            picante = ProductTag.objects.get(slug="picante")
            hamburguesa.tags.add(picante)
        except Product.DoesNotExist:
            pass
        except ProductTag.DoesNotExist:
            pass

        # Arepa con Queso -> Vegetariano
        try:
            arepa = Product.objects.get(name="Arepa con Queso")
            vegetariano = ProductTag.objects.get(slug="vegetariano")
            arepa.tags.add(vegetariano)
        except (Product.DoesNotExist, ProductTag.DoesNotExist):
            pass

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
            table_code: str | None,
            notes: str,
            items: list,
            paid: bool = False,
        ) -> Order:
            t = tables.get(table_code or "")
            order = OrderService.create(
                table_id=t.pk if t else None,
                notes=notes,
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
            "Mesa 1",
            "Sin cebolla",
            [("Hamburguesa", 2), ("Papas Fritas", 1), ("Agua Mineral", 2)],
            paid=True,
        )
        Order.objects.filter(pk=o1.pk).update(created_at=now - timedelta(hours=3))
        o2 = make("Mesa 2", "", [("Pizza", 1), ("Agua Mineral", 2)], paid=True)
        Order.objects.filter(pk=o2.pk).update(created_at=now - timedelta(hours=2))
        o3 = make(
            "Mesa 3",
            "Cumpleaños",
            [("Pizza", 3), ("Jugo de Lulo", 2), ("Limonada", 2)],
            paid=True,
        )
        Order.objects.filter(pk=o3.pk).update(
            created_at=now - timedelta(hours=1, minutes=30),
        )

        o4 = make(
            "Mesa 4",
            "",
            [("Hamburguesa", 3), ("Papas Fritas", 2)],
        )
        Order.objects.filter(pk=o4.pk).update(created_at=now - timedelta(minutes=45))
        o5 = make("Barra", "Para llevar", [("Arepa con Queso", 1), ("Jugo de Lulo", 1)])
        Order.objects.filter(pk=o5.pk).update(created_at=now - timedelta(minutes=15))
        o6 = make(None, "Domicilio", [("Empanadas", 2), ("Pizza", 2)])
        Order.objects.filter(pk=o6.pk).update(created_at=now - timedelta(minutes=5))

        items_m4 = list(OrderItem.objects.filter(order=o4).order_by("created_at"))
        for i, item in enumerate(items_m4):
            item.status = ["preparing", "ready", "preparing"][i]
            item.save()
        OrderItem.objects.filter(order=o5).update(status="preparing")

        OrderService.pay(o4.pk, "card", Decimal("20000"), "")

        self.stdout.write(
            f"  Demo: {Order.objects.count()} orders,"
            f" {OrderItem.objects.count()} items,"
            f" {Payment.objects.count()} payments"
        )
