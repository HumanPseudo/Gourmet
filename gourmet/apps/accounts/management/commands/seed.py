from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from gourmet.apps.accounts.models import Role
from gourmet.apps.menu.models import Category, Product
from gourmet.apps.tables.models import Table

User = get_user_model()


class Command(BaseCommand):
    help = "Seed initial data: roles, users, tables, menu items"

    def handle(self, *args, **options):
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
            ("Mesa 1", 2), ("Mesa 2", 4), ("Mesa 3", 4),
            ("Mesa 4", 6), ("Barra", 1),
        ]
        for code, capacity in tables_data:
            _, created = Table.objects.get_or_create(
                code=code, defaults={"capacity": capacity}
            )
            self.stdout.write(f"  {'Created' if created else 'Exists'} table: {code}")

        cat, _ = Category.objects.get_or_create(
            name="Bebidas", defaults={"sort_order": 1}
        )
        if _:
            self.stdout.write(f"  Created category: {cat.name}")

        products_data = [
            (cat, "Coca Cola", 2.50, "IVA_19"),
            (cat, "Agua Mineral", 1.50, "IVA_19"),
            (cat, "Jugo Natural", 3.00, "EXENTO"),
        ]
        cat2, _ = Category.objects.get_or_create(
            name="Comidas", defaults={"sort_order": 2}
        )
        if _:
            self.stdout.write(f"  Created category: {cat2.name}")

        products_data += [
            (cat2, "Hamburguesa", 8.50, "INC_8"),
            (cat2, "Pizza", 10.00, "INC_8"),
            (cat2, "Ensalada", 6.50, "EXENTO"),
            (cat2, "Papas Fritas", 4.00, "INC_8"),
        ]

        for category, name, price, tax_type in products_data:
            _, created = Product.objects.get_or_create(
                name=name,
                defaults={
                    "category": category,
                    "price": Decimal(str(price)),
                    "tax_type": tax_type,
                    "is_available": True,
                },
            )
            self.stdout.write(
                f"  {'Created' if created else 'Exists'}"
                f" product: {name} (${price}, {tax_type})"
            )

        self.stdout.write(self.style.SUCCESS("Seed complete"))
