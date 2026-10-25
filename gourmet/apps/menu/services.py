from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from uuid import UUID

from django.conf import settings
from django.db.models import Exists, F, OuterRef, QuerySet
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .models import (
    Category,
    OptionValue,
    Product,
    ProductOptionGroup,
)
from .schemas import CategoryIn, ProductIn


def get_menu_image_url(image_field) -> str:
    """
    Devuelve la URL pública de una imagen del menú.

    - Si hay storage S3 (Supabase) configurado, el campo FileField ya
      devuelve la URL absoluta vía `.url`.
    - Si es FileSystemStorage local, se concatena MENU_IMAGE_BASE_URL con
      el nombre relativo.
    """
    if not image_field:
        return ""
    try:
        url = image_field.url
    except (ValueError, AttributeError):
        return ""

    # Si ya es absoluta (S3/CDN), devolverla tal cual
    if url.startswith(("http://", "https://")):
        return url

    # Si es relativa (local), usar MENU_IMAGE_BASE_URL
    base = settings.MENU_IMAGE_BASE_URL.rstrip("/")
    # image_field.name contiene la ruta relativa dentro del storage
    rel_path = image_field.name.lstrip("/")
    return f"{base}/{rel_path}"


class CategoryService:
    @staticmethod
    def list() -> QuerySet[Category]:
        return Category.objects.all().order_by("sort_order", "name")

    @staticmethod
    def create(data: CategoryIn) -> Category:
        if Category.objects.filter(name=data.name).exists():
            raise ValueError("A category with this name already exists")
        return Category.objects.create(
            name=data.name,
            description=data.description,
            sort_order=data.sort_order,
            is_active=data.is_active,
        )

    @staticmethod
    def get(category_id: UUID) -> Category:
        return get_object_or_404(Category, pk=category_id)

    @staticmethod
    def update(category: Category, data: CategoryIn) -> Category:
        if (
            data.name != category.name
            and Category.objects.filter(name=data.name).exists()
        ):
            raise ValueError("A category with this name already exists")
        category.name = data.name
        category.description = data.description
        category.sort_order = data.sort_order
        category.is_active = data.is_active
        category.save()
        return category

    @staticmethod
    def delete(category: Category) -> None:
        category.delete()


class ProductService:
    @staticmethod
    def _base_queryset() -> QuerySet[Product]:
        return (
            Product.objects.select_related("category")
            .prefetch_related("tags", "option_attachments__option_group")
            .annotate(
                category_name=F("category__name"),
                has_options=Exists(
                    ProductOptionGroup.objects.filter(
                        product=OuterRef("pk"),
                        option_group__is_active=True,
                    )
                ),
            )
        )

    @staticmethod
    def list() -> QuerySet[Product]:
        return ProductService._base_queryset().order_by(
            "category__sort_order", "sort_order", "name"
        )

    @staticmethod
    def create(data: ProductIn) -> Product:
        category = get_object_or_404(Category, pk=data.category_id)
        product = Product.objects.create(
            category=category,
            name=data.name,
            description=data.description,
            price=data.price,
            tax_type=data.tax_type,
            is_available=data.is_available,
            sort_order=data.sort_order,
        )
        return ProductService.get(product.pk)

    @staticmethod
    def get(product_id: UUID) -> Product:
        return get_object_or_404(
            ProductService._base_queryset(),
            pk=product_id,
        )

    @staticmethod
    def update(product: Product, data: ProductIn) -> Product:
        product.category_id = data.category_id
        product.name = data.name
        product.description = data.description
        product.price = data.price
        product.tax_type = data.tax_type
        product.is_available = data.is_available
        product.sort_order = data.sort_order
        product.save()
        return ProductService.get(product.pk)

    @staticmethod
    def delete(product: Product) -> None:
        product.delete()


class MenuAvailabilityService:
    @staticmethod
    def is_category_available(category: Category, when=None) -> bool:
        if not category.is_active:
            return False

        rules = category.availability_rules.filter(is_active=True)
        if not rules.exists():
            return True

        now = when or timezone.localtime()
        current_date = now.date()
        current_time = now.time()
        weekday = now.weekday()

        for rule in rules:
            day_enabled = [
                rule.monday,
                rule.tuesday,
                rule.wednesday,
                rule.thursday,
                rule.friday,
                rule.saturday,
                rule.sunday,
            ][weekday]

            if not day_enabled:
                continue

            if rule.start_date and current_date < rule.start_date:
                continue

            if rule.end_date and current_date > rule.end_date:
                continue

            if rule.start_time and current_time < rule.start_time:
                continue

            if rule.end_time and current_time > rule.end_time:
                continue

            return True

        return False

    @staticmethod
    def is_product_orderable(product: Product, when=None) -> bool:
        if not product.is_available:
            return False

        if not product.category:
            return True

        return MenuAvailabilityService.is_category_available(product.category, when)


class MenuOptionService:
    @staticmethod
    def get_product_attachments(product: Product) -> QuerySet[ProductOptionGroup]:
        return (
            ProductOptionGroup.objects.filter(
                product=product,
                option_group__is_active=True,
            )
            .select_related(
                "option_group",
                "condition_parent",
                "condition_parent__option_group",
            )
            .prefetch_related(
                "option_group__values",
                "condition_values",
            )
            .order_by("sort_order", "option_group__name")
        )

    @staticmethod
    def validate_selection(
        product: Product,
        option_value_ids: list,
    ) -> tuple[list[dict], Decimal]:
        attachments = list(MenuOptionService.get_product_attachments(product))

        raw_ids = [str(value_id) for value_id in option_value_ids if value_id]
        unique_ids = list(dict.fromkeys(raw_ids))

        try:
            parsed_ids = [UUID(value_id) for value_id in unique_ids]
        except (TypeError, ValueError) as exc:
            raise ValueError("Opciones inválidas") from exc

        values = list(
            OptionValue.objects.filter(
                pk__in=parsed_ids,
                is_available=True,
                group__product_attachments__product=product,
            )
            .select_related("group")
            .distinct()
        )

        if len(values) != len(parsed_ids):
            raise ValueError("Hay opciones inválidas o no disponibles")

        selected_by_group: dict[UUID, list[OptionValue]] = defaultdict(list)
        for value in values:
            selected_by_group[value.group_id].append(value)

        attachments_by_id = {att.pk: att for att in attachments}
        attachments_by_group = {att.option_group_id: att for att in attachments}
        selected_ids = {value.pk for value in values}

        for group_id in selected_by_group:
            if group_id not in attachments_by_group:
                raise ValueError("Hay opciones que no pertenecen a este producto")

        memo: dict[UUID, bool] = {}

        def is_attachment_visible(
            attachment: ProductOptionGroup,
            depth: int = 0,
        ) -> bool:
            if attachment.pk in memo:
                return memo[attachment.pk]

            if depth > 10:
                memo[attachment.pk] = False
                return False

            if attachment.condition_parent_id is None:
                memo[attachment.pk] = True
                return True

            parent = attachments_by_id.get(attachment.condition_parent_id)
            if parent is None:
                memo[attachment.pk] = False
                return False

            if not is_attachment_visible(parent, depth + 1):
                memo[attachment.pk] = False
                return False

            condition_value_ids = {
                condition_value.pk
                for condition_value in attachment.condition_values.all()
            }

            visible = bool(condition_value_ids & selected_ids)
            memo[attachment.pk] = visible
            return visible

        selected_options: list[dict] = []
        price_delta = Decimal("0.00")

        for attachment in attachments:
            group = attachment.option_group
            selected_values = selected_by_group.get(group.pk, [])
            selected_values.sort(key=lambda value: (value.sort_order, value.name))
            visible = is_attachment_visible(attachment)

            if visible:
                min_required = group.min_selections
                if attachment.is_required and min_required < 1:
                    min_required = 1

                if len(selected_values) < min_required:
                    raise ValueError(
                        f"Debes elegir al menos una opción para {group.name}"
                    )

                if len(selected_values) > group.max_selections:
                    raise ValueError(
                        f"Excediste el máximo de opciones para {group.name}"
                    )

                for value in selected_values:
                    price_delta += value.price_delta
                    selected_options.append(
                        {
                            "group_id": str(group.pk),
                            "group_name": group.name,
                            "value_id": str(value.pk),
                            "value_name": value.name,
                            "price_delta": str(value.price_delta),
                        }
                    )
            else:
                if selected_values:
                    raise ValueError(
                        f"Las opciones seleccionadas de {group.name} "
                        "no están disponibles para la selección actual"
                    )

        selected_options.sort(key=lambda item: item["group_name"])
        return selected_options, price_delta.quantize(Decimal("0.01"))

    @staticmethod
    def pos_option_config(product: Product) -> dict:
        """Configuración JSON de opciones para el modal del POS."""
        attachments = MenuOptionService.get_product_attachments(product)
        groups: list[dict] = []
        conditions: list[dict] = []

        for attachment in attachments:
            group = attachment.option_group
            min_selections = group.min_selections
            if attachment.is_required and min_selections < 1:
                min_selections = 1

            available_values = [
                value for value in group.values.all() if value.is_available
            ]
            available_values.sort(key=lambda v: (v.sort_order, v.name))

            groups.append(
                {
                    "id": str(group.pk),
                    "name": group.name,
                    "required": attachment.is_required or min_selections > 0,
                    "min": min_selections,
                    "max": group.max_selections,
                    "multiple": group.selection_type == "multiple",
                    "values": [
                        {
                            "id": str(value.pk),
                            "name": value.name,
                            "price_delta": str(value.price_delta),
                        }
                        for value in available_values
                    ],
                }
            )

            if attachment.condition_parent is not None:
                conditions.append(
                    {
                        "group": str(group.pk),
                        "parent": str(attachment.condition_parent.option_group_id),
                        "values": [
                            str(condition_value.pk)
                            for condition_value in attachment.condition_values.all()
                        ],
                    }
                )

        return {
            "product_id": str(product.pk),
            "base_price": str(product.price),
            "groups": groups,
            "conditions": conditions,
        }
