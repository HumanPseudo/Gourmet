from __future__ import annotations

from typing import Any
from uuid import UUID

from django.http import HttpRequest
from ninja import Router
from ninja.pagination import paginate

from gourmet.apps.accounts.auth import AdminTokenAuth
from gourmet.apps.schemas import MessageOut

from .models import Product
from .schemas import CategoryIn, CategoryOut, ProductIn, ProductOut
from .services import CategoryService, ProductService

router = Router(auth=None)


# ── Category endpoints ─────────────────────────────────────────────────


@router.get(
    "/categories", response=list[CategoryOut], summary="List all categories"
)
@paginate
def list_categories(request: HttpRequest) -> Any:
    return CategoryService.list()


@router.post(
    "/categories",
    auth=AdminTokenAuth(),
    response={201: CategoryOut, 400: MessageOut},
    summary="Create a category",
)
def create_category(
    request: HttpRequest, payload: CategoryIn
) -> tuple[int, CategoryOut] | tuple[int, dict[str, str]]:
    try:
        cat = CategoryService.create(payload)
    except ValueError as e:
        return 400, {"detail": str(e)}
    return 201, CategoryOut.model_validate(cat)


@router.get(
    "/categories/{category_id}",
    response=CategoryOut,
    summary="Get category by ID",
)
def get_category(request: HttpRequest, category_id: UUID) -> CategoryOut:
    return CategoryOut.model_validate(CategoryService.get(category_id))


@router.put(
    "/categories/{category_id}",
    auth=AdminTokenAuth(),
    response={200: CategoryOut, 400: MessageOut},
    summary="Update a category",
)
def update_category(
    request: HttpRequest, category_id: UUID, payload: CategoryIn
) -> tuple[int, CategoryOut | dict[str, str]]:
    cat = CategoryService.get(category_id)
    try:
        updated = CategoryService.update(cat, payload)
    except ValueError as e:
        return 400, {"detail": str(e)}
    return 200, CategoryOut.model_validate(updated)


@router.delete(
    "/categories/{category_id}",
    auth=AdminTokenAuth(),
    response=MessageOut,
    summary="Delete a category",
)
def delete_category(request: HttpRequest, category_id: UUID) -> dict[str, str]:
    cat = CategoryService.get(category_id)
    CategoryService.delete(cat)
    return {"detail": "Category deleted"}


# ── Product endpoints ──────────────────────────────────────────────────


@router.get("/products", response=list[ProductOut], summary="List all products")
@paginate
def list_products(request: HttpRequest) -> Any:
    return ProductService.list()


@router.post(
    "/products",
    auth=AdminTokenAuth(),
    response={201: ProductOut, 400: MessageOut},
    summary="Create a product",
)
def create_product(
    request: HttpRequest, payload: ProductIn
) -> tuple[int, ProductOut] | tuple[int, dict[str, str]]:
    try:
        product = ProductService.create(payload)
    except ValueError as e:
        return 400, {"detail": str(e)}
    return 201, ProductOut.model_validate(product)


@router.get(
    "/products/{product_id}",
    response=ProductOut,
    summary="Get product by ID",
)
def get_product(request: HttpRequest, product_id: UUID) -> Product:
    return ProductService.get(product_id)


@router.put(
    "/products/{product_id}",
    auth=AdminTokenAuth(),
    response=ProductOut,
    summary="Update a product",
)
def update_product(
    request: HttpRequest, product_id: UUID, payload: ProductIn
) -> Product:
    product = ProductService.get(product_id)
    return ProductService.update(product, payload)


@router.delete(
    "/products/{product_id}",
    auth=AdminTokenAuth(),
    response=MessageOut,
    summary="Delete a product",
)
def delete_product(
    request: HttpRequest, product_id: UUID
) -> dict[str, str]:
    product = ProductService.get(product_id)
    ProductService.delete(product)
    return {"detail": "Product deleted"}
