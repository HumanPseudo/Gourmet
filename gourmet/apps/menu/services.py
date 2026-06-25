from __future__ import annotations

from uuid import UUID

from django.db.models import F, QuerySet
from django.shortcuts import get_object_or_404

from .models import Category, Product
from .schemas import CategoryIn, ProductIn


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
            .annotate(category_name=F("category__name"))
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
        product.is_available = data.is_available
        product.sort_order = data.sort_order
        product.save()
        return ProductService.get(product.pk)

    @staticmethod
    def delete(product: Product) -> None:
        product.delete()
