from __future__ import annotations

from decimal import Decimal

from django.core.management.base import BaseCommand

from gourmet.apps.menu.models import (
    Category,
    CategoryAvailabilityRule,
    OptionGroup,
    OptionValue,
    Product,
    ProductOptionGroup,
)


class Command(BaseCommand):
    help = "Seed demo menu for Commit 2: options, variants, and specials"

    def handle(self, *args, **options) -> None:
        self._create_categories()
        self._create_hamburguesas()
        self._create_almuerzo_ejecutivo()
        self._create_antojos()
        self._create_bebidas()
        self._create_perros_y_tablas()
        self._create_especiales_fin_de_semana()
        self.stdout.write(self.style.SUCCESS("Menu demo seed complete"))

    def _create_categories(self) -> None:
        categories = [
            ("Hamburguesas", 10),
            ("Almuerzos", 20),
            ("Antojos", 30),
            ("Bebidas", 40),
            ("Perros y Parrilla", 50),
            ("Especiales de Fin de Semana", 60),
        ]

        for name, sort_order in categories:
            Category.objects.get_or_create(
                name=name,
                defaults={"sort_order": sort_order, "is_active": True},
            )
            self.stdout.write(f"  Category: {name}")

    def _category(self, name: str) -> Category:
        return Category.objects.get(name=name)

    def _ensure_group(
        self,
        name: str,
        selection_type: str = OptionGroup.SelectionType.SINGLE,
        min_selections: int = 1,
        max_selections: int = 1,
        description: str = "",
    ) -> OptionGroup:
        group, created = OptionGroup.objects.update_or_create(
            name=name,
            defaults={
                "selection_type": selection_type,
                "min_selections": min_selections,
                "max_selections": max_selections,
                "description": description,
                "is_active": True,
            },
        )

        if created:
            self.stdout.write(f"  Created option group: {name}")

        return group

    def _ensure_value(
        self,
        group: OptionGroup,
        name: str,
        price_delta: str = "0.00",
        sort_order: int = 0,
    ) -> OptionValue:
        value, _ = OptionValue.objects.update_or_create(
            group=group,
            name=name,
            defaults={
                "price_delta": Decimal(price_delta),
                "sort_order": sort_order,
                "is_available": True,
            },
        )
        return value

    def _ensure_product(
        self,
        category: Category,
        name: str,
        price: str,
        tax_type: str = Product.TaxChoices.INC_8,
        description: str = "",
    ) -> Product:
        product, created = Product.objects.update_or_create(
            name=name,
            category=category,
            defaults={
                "price": Decimal(price),
                "tax_type": tax_type,
                "description": description,
                "is_available": True,
            },
        )

        if created:
            self.stdout.write(f"  Created product: {name}")

        return product

    def _attach_group(
        self,
        product: Product,
        group: OptionGroup,
        required: bool = False,
        sort_order: int = 0,
        condition_parent: ProductOptionGroup | None = None,
        condition_value_names: list[str] | None = None,
    ) -> ProductOptionGroup:
        attachment, _ = ProductOptionGroup.objects.update_or_create(
            product=product,
            option_group=group,
            defaults={
                "is_required": required,
                "sort_order": sort_order,
                "condition_parent": condition_parent,
            },
        )

        if condition_parent and condition_value_names:
            values = OptionValue.objects.filter(
                group=condition_parent.option_group,
                name__in=condition_value_names,
            )
            attachment.condition_values.set(values)
        else:
            attachment.condition_values.clear()

        return attachment

    def _create_hamburguesas(self) -> None:
        category = self._category("Hamburguesas")

        product = self._ensure_product(
            category,
            "Hamburguesa Criolla",
            "8500.00",
            description="Hamburguesa artesanal con ingredientes de la casa.",
        )

        size_group = self._ensure_group(
            "Hamburguesa: Variante y tamaño",
            OptionGroup.SelectionType.SINGLE,
            1,
            1,
        )
        self._ensure_value(size_group, "S (Pequeña)", "0.00", 1)
        self._ensure_value(size_group, "M (Mediana)", "1000.00", 2)
        self._ensure_value(size_group, "L (Grande)", "2000.00", 3)
        self._ensure_value(size_group, "Doble Carne", "3500.00", 4)
        self._ensure_value(size_group, "Triple Carne", "5000.00", 5)

        combo_group = self._ensure_group(
            "Hamburguesa: Opción de combo",
            OptionGroup.SelectionType.SINGLE,
            1,
            1,
        )
        self._ensure_value(combo_group, "Solo hamburguesa", "0.00", 1)
        self._ensure_value(combo_group, "En combo", "3000.00", 2)

        combo_side_group = self._ensure_group(
            "Hamburguesa: Acompañamiento combo",
            OptionGroup.SelectionType.SINGLE,
            1,
            1,
        )
        self._ensure_value(combo_side_group, "Papas a la francesa", "0.00", 1)
        self._ensure_value(combo_side_group, "Tajadas de plátano", "0.00", 2)

        cheese_group = self._ensure_group(
            "Hamburguesa: Adicionales de queso",
            OptionGroup.SelectionType.SINGLE,
            0,
            1,
            "Aplica exclusivamente para hamburguesas Doble y Triple.",
        )
        self._ensure_value(cheese_group, "+1 Porción de queso", "1000.00", 1)
        self._ensure_value(cheese_group, "+2 Porciones de queso", "2000.00", 2)
        self._ensure_value(cheese_group, "+3 Porciones de queso", "3000.00", 3)

        size_attachment = self._attach_group(
            product,
            size_group,
            required=True,
            sort_order=10,
        )

        combo_attachment = self._attach_group(
            product,
            combo_group,
            required=True,
            sort_order=20,
        )

        self._attach_group(
            product,
            combo_side_group,
            required=True,
            sort_order=30,
            condition_parent=combo_attachment,
            condition_value_names=["En combo"],
        )

        self._attach_group(
            product,
            cheese_group,
            required=False,
            sort_order=40,
            condition_parent=size_attachment,
            condition_value_names=["Doble Carne", "Triple Carne"],
        )

    def _create_almuerzo_ejecutivo(self) -> None:
        category = self._category("Almuerzos")

        product = self._ensure_product(
            category,
            "Almuerzo Ejecutivo Criollo",
            "18000.00",
            description=(
                "Incluye: 1 Sopa + 1 Principio + 1 Carne + 1 Bebida + "
                "Arroz blanco y Ensalada"
            ),
        )

        soup_group = self._ensure_group(
            "Almuerzo: Sopa",
            OptionGroup.SelectionType.SINGLE,
            1,
            1,
        )
        self._ensure_value(soup_group, "Sopa de plátano verde", "0.00", 1)
        self._ensure_value(soup_group, "Sancocho de res", "0.00", 2)
        self._ensure_value(soup_group, "Ajiaco tradicional", "0.00", 3)
        self._ensure_value(soup_group, "Sopa de mondongo", "0.00", 4)
        self._ensure_value(soup_group, "Crema de auyama", "0.00", 5)

        principle_group = self._ensure_group(
            "Almuerzo: Principio",
            OptionGroup.SelectionType.SINGLE,
            1,
            1,
        )
        self._ensure_value(principle_group, "Fríjoles rojos", "0.00", 1)
        self._ensure_value(principle_group, "Lentejas guisadas", "0.00", 2)
        self._ensure_value(principle_group, "Garbanzos con guiso", "0.00", 3)
        self._ensure_value(principle_group, "Arvejas verdes", "0.00", 4)
        self._ensure_value(principle_group, "Papa criolla chorreada", "0.00", 5)

        protein_group = self._ensure_group(
            "Almuerzo: Carne / Proteína",
            OptionGroup.SelectionType.SINGLE,
            1,
            1,
        )
        self._ensure_value(protein_group, "Pechuga de pollo a la plancha", "0.00", 1)
        self._ensure_value(protein_group, "Carne asada a la parrilla", "0.00", 2)
        self._ensure_value(protein_group, "Carne desmechada", "0.00", 3)
        self._ensure_value(protein_group, "Cerdo en salsa criolla", "0.00", 4)
        self._ensure_value(protein_group, "Filete de pescado frito", "0.00", 5)

        beverage_group = self._ensure_group(
            "Almuerzo: Bebida",
            OptionGroup.SelectionType.SINGLE,
            1,
            1,
        )
        self._ensure_value(beverage_group, "Limonada de la casa", "0.00", 1)
        self._ensure_value(beverage_group, "Agua de panela con limón", "0.00", 2)
        self._ensure_value(beverage_group, "Jugo de lulo en agua", "0.00", 3)

        self._attach_group(product, soup_group, True, 10)
        self._attach_group(product, principle_group, True, 20)
        self._attach_group(product, protein_group, True, 30)
        self._attach_group(product, beverage_group, True, 40)

    def _create_antojos(self) -> None:
        category = self._category("Antojos")

        simple_products = [
            ("Pandebono tradicional", "3000.00"),
            ("Buñuelo", "2500.00"),
            ("Almojábana", "2800.00"),
            ("Pan de queso", "2600.00"),
        ]

        for name, price in simple_products:
            self._ensure_product(category, name, price, Product.TaxChoices.EXENTO)

        empanada = self._ensure_product(
            category,
            "Empanada criolla de carne y papa",
            "2500.00",
        )
        empanada_addons = self._ensure_group(
            "Empanada: Adicionales",
            OptionGroup.SelectionType.MULTIPLE,
            0,
            3,
        )
        self._ensure_value(empanada_addons, "+Queso rallado", "1000.00", 1)
        self._ensure_value(empanada_addons, "+Guiso", "1500.00", 2)
        self._ensure_value(empanada_addons, "+Carne desmechada", "2500.00", 3)
        self._attach_group(empanada, empanada_addons, False, 10)

        arepa = self._ensure_product(
            category,
            "Arepa de choclo",
            "4500.00",
        )
        arepa_addons = self._ensure_group(
            "Arepa de choclo: Adicionales",
            OptionGroup.SelectionType.MULTIPLE,
            0,
            2,
        )
        self._ensure_value(arepa_addons, "+Queso campesino extra", "1500.00", 1)
        self._ensure_value(arepa_addons, "+Mantequilla doble", "1000.00", 2)
        self._attach_group(arepa, arepa_addons, False, 10)

        aborrajado = self._ensure_product(
            category,
            "Aborrajado valluno",
            "5000.00",
        )
        aborrajado_addons = self._ensure_group(
            "Aborrajado: Adicionales",
            OptionGroup.SelectionType.MULTIPLE,
            0,
            2,
        )
        self._ensure_value(aborrajado_addons, "+Queso extra", "1500.00", 1)
        self._ensure_value(aborrajado_addons, "+Bocadillo extra", "1200.00", 2)
        self._attach_group(aborrajado, aborrajado_addons, False, 10)

    def _create_bebidas(self) -> None:
        category = self._category("Bebidas")

        coffee = self._ensure_product(
            category,
            "Bebida de café",
            "3000.00",
        )
        coffee_varieties = self._ensure_group(
            "Café: Variedad",
            OptionGroup.SelectionType.SINGLE,
            1,
            1,
        )
        self._ensure_value(coffee_varieties, "Café negro / Tinto", "0.00", 1)
        self._ensure_value(coffee_varieties, "Café con leche", "500.00", 2)
        self._ensure_value(coffee_varieties, "Cappuccino", "1000.00", 3)
        self._ensure_value(coffee_varieties, "Perico / Pintado", "500.00", 4)

        coffee_sizes = self._ensure_group(
            "Café: Tamaño",
            OptionGroup.SelectionType.SINGLE,
            1,
            1,
        )
        self._ensure_value(coffee_sizes, "S (Pequeño)", "0.00", 1)
        self._ensure_value(coffee_sizes, "M (Mediano)", "1000.00", 2)
        self._ensure_value(coffee_sizes, "L (Grande)", "2000.00", 3)

        self._attach_group(coffee, coffee_varieties, True, 10)
        self._attach_group(coffee, coffee_sizes, True, 20)

        juice = self._ensure_product(
            category,
            "Jugo natural",
            "4000.00",
        )

        juice_varieties = self._ensure_group(
            "Jugo: Variedad",
            OptionGroup.SelectionType.SINGLE,
            1,
            1,
        )
        self._ensure_value(juice_varieties, "Maracuyá", "0.00", 1)
        self._ensure_value(juice_varieties, "Mango", "0.00", 2)
        self._ensure_value(juice_varieties, "Lulo", "0.00", 3)
        self._ensure_value(juice_varieties, "Mora", "0.00", 4)
        self._ensure_value(juice_varieties, "Limonada natural", "0.00", 5)

        juice_base = self._ensure_group(
            "Jugo: Base",
            OptionGroup.SelectionType.SINGLE,
            1,
            1,
        )
        self._ensure_value(juice_base, "En agua", "0.00", 1)
        self._ensure_value(juice_base, "En leche", "500.00", 2)

        juice_sizes = self._ensure_group(
            "Jugo: Tamaño",
            OptionGroup.SelectionType.SINGLE,
            1,
            1,
        )
        self._ensure_value(juice_sizes, "S (Pequeño)", "0.00", 1)
        self._ensure_value(juice_sizes, "M (Mediano)", "1000.00", 2)
        self._ensure_value(juice_sizes, "L (Grande)", "2000.00", 3)

        self._attach_group(juice, juice_varieties, True, 10)
        self._attach_group(juice, juice_base, True, 20)
        self._attach_group(juice, juice_sizes, True, 30)

    def _create_perros_y_tablas(self) -> None:
        category = self._category("Perros y Parrilla")

        hotdog = self._ensure_product(
            category,
            "Perro Caliente",
            "7000.00",
        )

        hotdog_base = self._ensure_group(
            "Perro: Base",
            OptionGroup.SelectionType.SINGLE,
            1,
            1,
        )
        self._ensure_value(hotdog_base, "Perro Sencillo", "0.00", 1)
        self._ensure_value(hotdog_base, "Perro Especial", "2000.00", 2)

        hotdog_toppings = self._ensure_group(
            "Perro: Adicionales y toppings",
            OptionGroup.SelectionType.MULTIPLE,
            0,
            5,
        )
        self._ensure_value(hotdog_toppings, "Queso costeño rallado", "1000.00", 1)
        self._ensure_value(hotdog_toppings, "Papa fosforito", "800.00", 2)
        self._ensure_value(hotdog_toppings, "Tocineta picada", "1500.00", 3)
        self._ensure_value(hotdog_toppings, "Maíz tierno", "700.00", 4)

        hotdog_eggs = self._ensure_group(
            "Perro: Huevos de codorniz",
            OptionGroup.SelectionType.SINGLE,
            0,
            1,
        )
        self._ensure_value(hotdog_eggs, "1 huevo de codorniz", "500.00", 1)
        self._ensure_value(hotdog_eggs, "2 huevos de codorniz", "1000.00", 2)
        self._ensure_value(hotdog_eggs, "3 huevos de codorniz", "1500.00", 3)

        sauces = self._ensure_group(
            "Perro: Salsas",
            OptionGroup.SelectionType.MULTIPLE,
            0,
            6,
        )
        self._ensure_value(sauces, "Chimichurri artesanal", "0.00", 1)
        self._ensure_value(sauces, "Salsa de ajo", "0.00", 2)
        self._ensure_value(sauces, "Salsa rosada casera", "0.00", 3)
        self._ensure_value(sauces, "Salsa de piña", "0.00", 4)
        self._ensure_value(sauces, "Salsa tártara", "0.00", 5)
        self._ensure_value(sauces, "Ají picante casero", "0.00", 6)

        self._attach_group(hotdog, hotdog_base, True, 10)
        self._attach_group(hotdog, hotdog_toppings, False, 20)
        self._attach_group(hotdog, hotdog_eggs, False, 30)
        self._attach_group(hotdog, sauces, False, 40)

        meat_board = self._ensure_product(
            category,
            "Tabla de Carne a la Parrilla",
            "25000.00",
        )

        cuts = self._ensure_group(
            "Tabla: Corte",
            OptionGroup.SelectionType.SINGLE,
            1,
            1,
        )
        self._ensure_value(cuts, "Lomo fino", "5000.00", 1)
        self._ensure_value(cuts, "Chatas / Churrasco", "0.00", 2)
        self._ensure_value(cuts, "Punta de anca", "2000.00", 3)
        self._ensure_value(cuts, "Pechuga a la parrilla", "0.00", 4)

        portions = self._ensure_group(
            "Tabla: Tamaño / Porción",
            OptionGroup.SelectionType.SINGLE,
            1,
            1,
        )
        self._ensure_value(portions, "Personal (250g)", "0.00", 1)
        self._ensure_value(portions, "Mediana (350g)", "8000.00", 2)
        self._ensure_value(portions, "Familiar (500g)", "18000.00", 3)

        terms = self._ensure_group(
            "Tabla: Término de cocción",
            OptionGroup.SelectionType.SINGLE,
            1,
            1,
        )
        self._ensure_value(terms, "Azul / Cárnico", "0.00", 1)
        self._ensure_value(terms, "Medio (1/2)", "0.00", 2)
        self._ensure_value(terms, "Tres cuartos (3/4)", "0.00", 3)
        self._ensure_value(terms, "Bien asado / Bien cocido", "0.00", 4)

        sides = self._ensure_group(
            "Tabla: Acompañantes",
            OptionGroup.SelectionType.MULTIPLE,
            0,
            2,
        )
        self._ensure_value(sides, "Papa francesa", "0.00", 1)
        self._ensure_value(sides, "Papa criolla", "0.00", 2)
        self._ensure_value(sides, "Papa al horno", "0.00", 3)
        self._ensure_value(sides, "Arepa con queso", "0.00", 4)
        self._ensure_value(
            sides,
            "Plátano maduro con queso y guiso",
            "0.00",
            5,
        )

        board_sauce = self._ensure_group(
            "Tabla: Salsa de acompañamiento",
            OptionGroup.SelectionType.SINGLE,
            1,
            1,
        )
        self._ensure_value(board_sauce, "Chimichurri artesanal", "0.00", 1)
        self._ensure_value(board_sauce, "Salsa de ajo", "0.00", 2)
        self._ensure_value(board_sauce, "Salsa rosada casera", "0.00", 3)
        self._ensure_value(board_sauce, "Salsa de piña", "0.00", 4)
        self._ensure_value(board_sauce, "Salsa tártara", "0.00", 5)
        self._ensure_value(board_sauce, "Ají picante casero", "0.00", 6)

        self._attach_group(meat_board, cuts, True, 10)
        self._attach_group(meat_board, portions, True, 20)
        self._attach_group(meat_board, terms, True, 30)
        self._attach_group(meat_board, sides, False, 40)
        self._attach_group(meat_board, board_sauce, True, 50)

    def _create_especiales_fin_de_semana(self) -> None:
        category = self._category("Especiales de Fin de Semana")

        specials = [
            (
                "Picada Criolla Familiar",
                "45000.00",
                "Res, cerdo, chicharrón, chorizo, papa criolla y patacón.",
            ),
            (
                "Churrasco a la Parrilla",
                "32000.00",
                "Con chimichurri, papa al horno y ensalada.",
            ),
            (
                "Pargo Frito",
                "38000.00",
                "Con arroz de coco, patacones y saladillo.",
            ),
            (
                "Cazuela de Mariscos",
                "42000.00",
                "Al estilo costeño.",
            ),
        ]

        for name, price, description in specials:
            self._ensure_product(
                category,
                name,
                price,
                description=description,
            )

        CategoryAvailabilityRule.objects.update_or_create(
            category=category,
            name="Solo fin de semana",
            defaults={
                "is_active": True,
                "monday": False,
                "tuesday": False,
                "wednesday": False,
                "thursday": False,
                "friday": False,
                "saturday": True,
                "sunday": True,
                "badge_text": "Especial de fin de semana",
                "sort_order": 10,
            },
        )

        self.stdout.write("  Weekend availability rule created")
