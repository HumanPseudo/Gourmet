from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from ninja import Router, Schema

from gourmet.apps.accounts.auth import AdminTokenAuth
from gourmet.apps.schemas import MessageOut

from .models import Category, Product

router = Router(auth=None)


# ── Schemas ────────────────────────────────────────────────────────────


class CategoryOut(Schema):
    id: UUID
    name: str
    description: str | None = None
    sort_order: int
    is_active: bool


class CategoryIn(Schema):
    name: str
    description: str | None = None
    sort_order: int = 0
    is_active: bool = True


class ProductOut(Schema):
    id: UUID
    category_id: UUID
    category_name: str
    name: str
    description: str | None = None
    price: Decimal
    is_available: bool
    sort_order: int


class ProductIn(Schema):
    category_id: UUID
    name: str
    description: str | None = None
    price: Decimal
    is_available: bool = True
    sort_order: int = 0


# ── Category endpoints ─────────────────────────────────────────────────


@router.get("/categories", response=list[CategoryOut], summary="List all categories")
def list_categories(request: HttpRequest) -> list[CategoryOut]:
    return [
        CategoryOut(
            id=c.pk, name=c.name, description=c.description,
            sort_order=c.sort_order, is_active=c.is_active,
        )
        for c in Category.objects.all().order_by("sort_order", "name")
    ]


@router.post(
    "/categories", auth=AdminTokenAuth(),
    response={201: CategoryOut, 400: MessageOut},
    summary="Create a category",
)
def create_category(
    request: HttpRequest, payload: CategoryIn
) -> tuple[int, CategoryOut] | tuple[int, dict[str, str]]:
    if Category.objects.filter(name=payload.name).exists():
        return 400, {"detail": "A category with this name already exists"}
    cat = Category.objects.create(
        name=payload.name, description=payload.description,
        sort_order=payload.sort_order, is_active=payload.is_active,
    )
    return 201, CategoryOut(
        id=cat.pk, name=cat.name, description=cat.description,
        sort_order=cat.sort_order, is_active=cat.is_active,
    )


@router.get(
    "/categories/{category_id}", response=CategoryOut,
    summary="Get category by ID",
)
def get_category(request: HttpRequest, category_id: UUID) -> CategoryOut:
    cat = get_object_or_404(Category, pk=category_id)
    return CategoryOut(
        id=cat.pk, name=cat.name, description=cat.description,
        sort_order=cat.sort_order, is_active=cat.is_active,
    )


@router.put(
    "/categories/{category_id}", auth=AdminTokenAuth(),
    response=CategoryOut, summary="Update a category",
)
def update_category(
    request: HttpRequest, category_id: UUID, payload: CategoryIn
) -> CategoryOut:
    cat = get_object_or_404(Category, pk=category_id)
    cat.name = payload.name
    cat.description = payload.description
    cat.sort_order = payload.sort_order
    cat.is_active = payload.is_active
    cat.save()
    return CategoryOut(
        id=cat.pk, name=cat.name, description=cat.description,
        sort_order=cat.sort_order, is_active=cat.is_active,
    )


@router.delete(
    "/categories/{category_id}", auth=AdminTokenAuth(),
    response=MessageOut, summary="Delete a category",
)
def delete_category(request: HttpRequest, category_id: UUID) -> dict[str, str]:
    cat = get_object_or_404(Category, pk=category_id)
    cat.delete()
    return {"detail": "Category deleted"}


# ── Product endpoints ──────────────────────────────────────────────────


def product_to_out(product: Product) -> ProductOut:
    return ProductOut(
        id=product.pk,
        category_id=product.category_id,
        category_name=product.category.name,
        name=product.name,
        description=product.description,
        price=product.price,
        is_available=product.is_available,
        sort_order=product.sort_order,
    )


@router.get("/products", response=list[ProductOut], summary="List all products")
def list_products(request: HttpRequest) -> list[ProductOut]:
    qs = (
        Product.objects.select_related("category")
        .all()
        .order_by("category__sort_order", "sort_order", "name")
    )
    return [product_to_out(p) for p in qs]


@router.post(
    "/products", auth=AdminTokenAuth(),
    response={201: ProductOut, 400: MessageOut},
    summary="Create a product",
)
def create_product(
    request: HttpRequest, payload: ProductIn
) -> tuple[int, ProductOut] | tuple[int, dict[str, str]]:
    cat = get_object_or_404(Category, pk=payload.category_id)
    product = Product.objects.create(
        category=cat, name=payload.name, description=payload.description,
        price=payload.price, is_available=payload.is_available,
        sort_order=payload.sort_order,
    )
    return 201, product_to_out(product)


@router.get("/products/{product_id}", response=ProductOut, summary="Get product by ID")
def get_product(request: HttpRequest, product_id: UUID) -> ProductOut:
    product = get_object_or_404(
        Product.objects.select_related("category"),
        pk=product_id,
    )
    return product_to_out(product)


@router.put(
    "/products/{product_id}", auth=AdminTokenAuth(),
    response=ProductOut, summary="Update a product",
)
def update_product(
    request: HttpRequest, product_id: UUID, payload: ProductIn
) -> ProductOut:
    product = get_object_or_404(
        Product.objects.select_related("category"),
        pk=product_id,
    )
    product.category_id = payload.category_id
    product.name = payload.name
    product.description = payload.description
    product.price = payload.price
    product.is_available = payload.is_available
    product.sort_order = payload.sort_order
    product.save()
    return product_to_out(product)


@router.delete(
    "/products/{product_id}", auth=AdminTokenAuth(),
    response=MessageOut, summary="Delete a product",
)
def delete_product(request: HttpRequest, product_id: UUID) -> dict[str, str]:
    product = get_object_or_404(Product, pk=product_id)
    product.delete()
    return {"detail": "Product deleted"}
