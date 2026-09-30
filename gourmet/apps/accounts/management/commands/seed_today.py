# ruff: noqa: E501
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from gourmet.apps.accounts.models import Role
from gourmet.apps.inventory.models import (
    InventoryItem,
    InventoryMovement,
    ProductRecipe,
)
from gourmet.apps.menu.models import Category, Product
from gourmet.apps.orders.models import DailyClose, Order, OrderItem, Payment
from gourmet.apps.orders.services import OrderService
from gourmet.apps.tables.models import Table

User = get_user_model()


class Command(BaseCommand):
    help = "Seed today's test data: inventory, orders, payments, kitchen, daily close"

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

        # Mesas
        tables_data = [
            ("Mesa 1", 2),
            ("Mesa 2", 4),
            ("Mesa 3", 4),
            ("Mesa 4", 6),
            ("Mesa 5", 8),
            ("Barra", 1),
            ("Terraza 1", 4),
            ("Terraza 2", 4),
            ("VIP", 12),
        ]
        for code, capacity in tables_data:
            Table.objects.get_or_create(code=code, defaults={"capacity": capacity})

        # Categorías
        cat_bebidas, _ = Category.objects.get_or_create(
            name="Bebidas", defaults={"sort_order": 1}
        )
        cat_comidas, _ = Category.objects.get_or_create(
            name="Comidas", defaults={"sort_order": 2}
        )
        cat_postres, _ = Category.objects.get_or_create(
            name="Postres", defaults={"sort_order": 3}
        )
        cat_entradas, _ = Category.objects.get_or_create(
            name="Entradas", defaults={"sort_order": 0}
        )

        # Productos (COP)
        products_data = [
            (cat_entradas, "Ceviche", 18500, "INC_8"),
            (cat_entradas, "Empanadas (x3)", 8500, "INC_8"),
            (cat_entradas, "Patacones con Hogao", 10500, "EXENTO"),
            (cat_comidas, "Hamburguesa Clásica", 22500, "INC_8"),
            (cat_comidas, "Hamburguesa BBQ", 26500, "INC_8"),
            (cat_comidas, "Pizza Personal", 18000, "INC_8"),
            (cat_comidas, "Pizza Familiar", 36000, "INC_8"),
            (cat_comidas, "Bandeja Paisa", 28500, "INC_8"),
            (cat_comidas, "Ajiaco", 19500, "EXENTO"),
            (cat_comidas, "Ensalada Caesar", 14000, "EXENTO"),
            (cat_comidas, "Papas Fritas", 8500, "INC_8"),
            (cat_comidas, "Arroz con Pollo", 16500, "INC_8"),
            (cat_bebidas, "Agua Mineral", 2500, "IVA_19"),
            (cat_bebidas, "Jugo Natural de Naranja", 7000, "EXENTO"),
            (cat_bebidas, "Limonada", 5000, "EXENTO"),
            (cat_postres, "Flan Napolitano", 9500, "INC_8"),
            (cat_postres, "Tres Leches", 8500, "EXENTO"),
            (cat_postres, "Helado (2 bolas)", 6500, "INC_8"),
        ]
        prods = {}
        for cat, name, price, tax_type in products_data:
            p, _ = Product.objects.get_or_create(
                name=name,
                defaults={
                    "category": cat,
                    "price": Decimal(str(price)),
                    "tax_type": tax_type,
                    "is_available": True,
                },
            )
            prods[name] = p

        # Inventario
        inv_data = {
            "Carne de res (kg)": (15, 2, 28000),
            "Pan de hamburguesa": (40, 10, 1200),
            "Tocineta (kg)": (5, 1, 18000),
            "Queso mozzarella (kg)": (8, 2, 15000),
            "Masa de pizza": (20, 5, 3000),
            "Pechuga de pollo (kg)": (10, 2, 15000),
            "Arroz (kg)": (25, 5, 3500),
            "Frijol (kg)": (10, 3, 5000),
            "Papa (kg)": (30, 5, 2000),
            "Yuca (kg)": (8, 2, 2500),
            "Lechuga (kg)": (5, 1, 3000),
            "Tomate (kg)": (6, 1, 3500),
            "Cebolla (kg)": (8, 2, 2000),
            "Aceite de cocina (litro)": (10, 2, 6000),
            "Naranja (kg)": (10, 3, 3000),
            "Limón (kg)": (5, 1, 4000),
            "Leche condensada (lata)": (10, 2, 4500),
            "Panela (kg)": (3, 1, 3500),
            "Crema de leche (litro)": (5, 1, 6500),
            "Helado (kg)": (6, 2, 12000),
            "Huevos (unidad)": (60, 12, 500),
            "Plátano verde (kg)": (8, 2, 2000),
        }
        inv_items = {}
        for name, (stock, min_stock, cost) in inv_data.items():
            item, _ = InventoryItem.objects.get_or_create(
                name=name,
                defaults={
                    "unit": name.split("(")[-1].rstrip(")") if "(" in name else "unit",
                    "stock": Decimal(str(stock)),
                    "min_stock": Decimal(str(min_stock)),
                    "cost_price": Decimal(str(cost)),
                },
            )
            inv_items[name] = item

        # Recetas
        recipes: list[tuple[str, list[tuple[str, int | float]]]] = [
            (
                "Hamburguesa Clásica",
                [
                    ("Pan de hamburguesa", 1),
                    ("Carne de res (kg)", 0.15),
                    ("Lechuga (kg)", 0.03),
                    ("Tomate (kg)", 0.04),
                    ("Cebolla (kg)", 0.02),
                ],
            ),
            (
                "Hamburguesa BBQ",
                [
                    ("Pan de hamburguesa", 1),
                    ("Carne de res (kg)", 0.18),
                    ("Tocineta (kg)", 0.04),
                    ("Lechuga (kg)", 0.03),
                    ("Tomate (kg)", 0.04),
                    ("Cebolla (kg)", 0.02),
                ],
            ),
            ("Pizza Personal", [("Masa de pizza", 1), ("Queso mozzarella (kg)", 0.15)]),
            ("Pizza Familiar", [("Masa de pizza", 2), ("Queso mozzarella (kg)", 0.3)]),
            (
                "Bandeja Paisa",
                [
                    ("Arroz (kg)", 0.2),
                    ("Frijol (kg)", 0.15),
                    ("Carne de res (kg)", 0.2),
                    ("Plátano verde (kg)", 0.1),
                    ("Huevos (unidad)", 1),
                ],
            ),
            (
                "Ajiaco",
                [
                    ("Papa (kg)", 0.25),
                    ("Pechuga de pollo (kg)", 0.15),
                    ("Crema de leche (litro)", 0.05),
                ],
            ),
            ("Ensalada Caesar", [("Lechuga (kg)", 0.15), ("Tomate (kg)", 0.05)]),
            ("Papas Fritas", [("Papa (kg)", 0.3), ("Aceite de cocina (litro)", 0.02)]),
            ("Arroz con Pollo", [("Arroz (kg)", 0.2), ("Pechuga de pollo (kg)", 0.15)]),
            ("Jugo Natural de Naranja", [("Naranja (kg)", 0.4)]),
            ("Limonada", [("Limón (kg)", 0.15)]),
            (
                "Tres Leches",
                [("Leche condensada (lata)", 0.5), ("Crema de leche (litro)", 0.1)],
            ),
            ("Helado (2 bolas)", [("Helado (kg)", 0.15)]),
        ]
        for prod_name, ingredients in recipes:
            product = prods[prod_name]
            for ing_name, qty in ingredients:
                ProductRecipe.objects.get_or_create(
                    product=product,
                    item=inv_items[ing_name],
                    defaults={"quantity": Decimal(str(qty))},
                )

        self._create_today_data()
        self.stdout.write(self.style.SUCCESS("Today's seed data created"))

    def _create_today_data(self) -> None:
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today_start + timedelta(days=1)

        # cleanup previous seed for today
        Order.objects.filter(
            created_at__gte=today_start, created_at__lt=tomorrow
        ).delete()
        DailyClose.objects.filter(closed_at__gte=today_start).delete()
        for m in InventoryMovement.objects.filter(
            reference__in=["order:auto", "cocina:preparado"],
            created_at__gte=today_start,
        ):
            m.item.stock += m.quantity
            m.item.save(update_fields=["stock"])
            m.delete()

        tables = {t.code: t for t in Table.objects.filter(is_active=True)}
        prods = {p.name: p for p in Product.objects.filter(is_available=True)}

        def make(table_code, notes, items, paid=False, customer_name=""):
            t = tables.get(table_code or "")
            order = OrderService.create(
                table_id=t.pk if t else None,
                notes=notes,
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

        o1 = make(
            "Mesa 1",
            "Sin cebolla",
            [
                ("Hamburguesa Clásica", 2),
                ("Gaseosa personal", 2),
                ("Papas Fritas", 1),
            ],
            paid=True,
            customer_name="Carlos",
        )
        Order.objects.filter(pk=o1.pk).update(
            created_at=today_start + timedelta(hours=10)
        )
        Order.objects.filter(pk=o1.pk).update(
            closed_at=today_start + timedelta(hours=11)
        )

        o2 = make(
            "Mesa 2",
            "",
            [("Pizza Personal", 1), ("Agua Cristal", 2), ("Limonada", 1)],
            paid=True,
            customer_name="Ana",
        )
        Order.objects.filter(pk=o2.pk).update(
            created_at=today_start + timedelta(hours=11)
        )
        Order.objects.filter(pk=o2.pk).update(
            closed_at=today_start + timedelta(hours=11, minutes=45)
        )

        o3 = make(
            "Mesa 3",
            "Cumpleaños — traer vela",
            [
                ("Pizza Familiar", 1),
                ("Gaseosa litro", 2),
                ("Helado (2 bolas)", 4),
                ("Tres Leches", 1),
            ],
            paid=True,
            customer_name="Familia Pérez",
        )
        Order.objects.filter(pk=o3.pk).update(
            created_at=today_start + timedelta(hours=12)
        )
        Order.objects.filter(pk=o3.pk).update(
            closed_at=today_start + timedelta(hours=13, minutes=30)
        )

        o4 = make(
            "Mesa 4",
            "",
            [("Bandeja Paisa", 2), ("Ajiaco", 1), ("Limonada", 3)],
            customer_name="Pedro",
        )
        Order.objects.filter(pk=o4.pk).update(
            created_at=today_start + timedelta(hours=13)
        )
        o5 = make(
            "Barra",
            "Para llevar",
            [
                ("Ensalada Caesar", 1),
                ("Jugo Natural de Naranja", 2),
                ("Empanadas (x3)", 2),
            ],
            customer_name="Llevar",
        )
        Order.objects.filter(pk=o5.pk).update(
            created_at=today_start + timedelta(hours=14)
        )
        o6 = make(
            "Mesa 5",
            "",
            [("Hamburguesa BBQ", 3), ("Cerveza artesanal", 3)],
            customer_name="Juan",
        )
        Order.objects.filter(pk=o6.pk).update(
            created_at=today_start + timedelta(hours=14, minutes=30)
        )
        o7 = make(
            "Terraza 1",
            "",
            [
                ("Ceviche", 2),
                ("Arroz con Pollo", 2),
                ("Gaseosa litro", 1),
                ("Cerveza clara", 2),
            ],
            paid=True,
        )
        Order.objects.filter(pk=o7.pk).update(
            created_at=today_start + timedelta(hours=12, minutes=30)
        )
        Order.objects.filter(pk=o7.pk).update(
            closed_at=today_start + timedelta(hours=14)
        )
        o8 = make(
            "VIP",
            "Reserva especial",
            [
                ("Bandeja Paisa", 4),
                ("Ajiaco", 2),
                ("Ceviche", 3),
                ("Gaseosa litro", 4),
                ("Cerveza artesanal", 6),
                ("Tres Leches", 3),
            ],
            customer_name="Empresa XYZ",
        )
        Order.objects.filter(pk=o8.pk).update(
            created_at=today_start + timedelta(hours=13, minutes=30)
        )

        Order.objects.filter(pk=o8.pk).update(
            notes="Reserva especial — Empresa XYZ (12 personas)"
        )

        items_o4 = list(OrderItem.objects.filter(order=o4).order_by("created_at"))
        for i, item in enumerate(items_o4):
            status = ["preparing", "ready", "preparing"][i]
            OrderService.set_item_status(o4.pk, item.pk, status)
        for item in OrderItem.objects.filter(order=o5):
            OrderService.set_item_status(o5.pk, item.pk, "preparing")

        OrderService.pay(o4.pk, "card", Decimal("50000"), "")
        OrderService.pay(o6.pk, "card", Decimal("30000"), "")

        total_sales = sum(
            (o.total for o in Order.objects.filter(status=Order.Status.CLOSED)),
            Decimal("0"),
        )
        total_cash = sum(
            (p.amount for p in Payment.objects.filter(method="cash")),
            Decimal("0"),
        )
        DailyClose.objects.create(
            closed_by=User.objects.filter(is_superuser=True).first(),
            total_sales=total_sales,
            total_cash=total_cash,
            cash_opening=Decimal("200000.00"),
            cash_counted=Decimal("650000.00"),
        )

        self.stdout.write(
            f"  Today: {Order.objects.count()} orders,"
            f" {OrderItem.objects.count()} items,"
            f" {Payment.objects.count()} payments,"
            f" {DailyClose.objects.count()} daily closes"
        )
