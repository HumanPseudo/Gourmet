from __future__ import annotations

import os
import uuid
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify

# Validador para formatos de imagen permitidos
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".jfif"}
MAX_IMAGE_SIZE = 2 * 1024 * 1024  # 2 MB


def validate_image_extension(value) -> None:
    """Valida que la extensión del archivo esté permitida."""
    ext = os.path.splitext(value.name)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError(
            f"Formato de imagen no permitido: {ext}. "
            f"Formatos válidos: {', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))}"
        )


def validate_image_size(value) -> None:
    """Valida que el tamaño del archivo no exceda 2 MB."""
    if value.size > MAX_IMAGE_SIZE:
        size_mb = value.size / (1024 * 1024)
        raise ValidationError(
            f"La imagen es muy pesada ({size_mb:.1f} MB). "
            f"Tamaño máximo permitido: 2 MB."
        )


def menu_image_upload_to(instance: Product, filename: str) -> str:
    """Ruta de almacenamiento para imágenes de menú."""
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".jfif":
        ext = ".jpg"
    cat_slug = slugify(instance.category.name) if instance.category else "misc"
    prod_slug = slugify(instance.name) or "producto"
    short_uuid = uuid.uuid4().hex[:8]
    return f"menu/{cat_slug}/{prod_slug}-{short_uuid}{ext}"


def validate_svg_extension(value) -> None:
    """Valida que el archivo sea SVG."""
    ext = os.path.splitext(value.name)[1].lower()
    if ext != ".svg":
        raise ValidationError(
            f"El icono del badge debe ser un archivo SVG. Recibido: {ext}"
        )


def badge_icon_upload_to(instance: ProductTag, filename: str) -> str:
    """Ruta de almacenamiento para iconos SVG de badges."""
    ext = os.path.splitext(filename)[1].lower()
    slug = slugify(instance.slug or instance.name) or "badge"
    return f"badges/{slug}{ext}"


class Category(models.Model):
    id: models.UUIDField[uuid.UUID, uuid.UUID] = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    name: models.CharField[str, str] = models.CharField(
        max_length=100, unique=True, verbose_name="Name"
    )
    description: models.TextField[str | None, str | None] = models.TextField(
        blank=True, null=True, verbose_name="Description"
    )
    sort_order: models.IntegerField[int, int] = models.IntegerField(
        default=0, verbose_name="Order"
    )
    is_active: models.BooleanField[bool, bool] = models.BooleanField(
        default=True, verbose_name="Active"
    )
    created_at: models.DateTimeField[Any, Any] = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField[Any, Any] = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name


class ProductTag(models.Model):
    """Badge/etiqueta para productos (ej: Vegetariano, Picante, Nuevo)."""

    id: models.UUIDField[uuid.UUID, uuid.UUID] = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    name: models.CharField[str, str] = models.CharField(
        max_length=50, unique=True, verbose_name="Name"
    )
    slug: models.SlugField[str, str] = models.SlugField(
        max_length=50, unique=True, verbose_name="Slug"
    )
    description: models.TextField[str | None, str | None] = models.TextField(
        blank=True, verbose_name="Description"
    )
    icon: models.FileField = models.FileField(
        upload_to=badge_icon_upload_to,
        validators=[validate_svg_extension],
        verbose_name="Icon (SVG)",
        help_text="Debe ser un archivo SVG. Obligatorio.",
    )
    color: models.CharField[str, str] = models.CharField(
        max_length=20,
        default="#28a745",
        verbose_name="Color (hex)",
        help_text="Color hex para el badge, ej: #28a745",
    )
    sort_order: models.IntegerField[int, int] = models.IntegerField(
        default=0, verbose_name="Order"
    )
    is_active: models.BooleanField[bool, bool] = models.BooleanField(
        default=True, verbose_name="Active"
    )
    created_at: models.DateTimeField[Any, Any] = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField[Any, Any] = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Product Tag"
        verbose_name_plural = "Product Tags"
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Product(models.Model):
    class TaxChoices(models.TextChoices):
        INC_8 = "INC_8", "Impuesto al Consumo 8%"
        IVA_19 = "IVA_19", "IVA 19%"
        IVA_5 = "IVA_5", "IVA 5%"
        EXENTO = "EXENTO", "Exento 0%"

    id: models.UUIDField[uuid.UUID, uuid.UUID] = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    category: models.ForeignKey[Category, Category] = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="products",
        verbose_name="Category",
    )
    category_id: uuid.UUID
    name: models.CharField[str, str] = models.CharField(
        max_length=200, verbose_name="Name"
    )
    description: models.TextField[str | None, str | None] = models.TextField(
        blank=True, null=True, verbose_name="Description"
    )
    price: models.DecimalField[Decimal, Decimal] = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Price"
    )
    tax_type: models.CharField[str, str] = models.CharField(
        max_length=8,
        choices=TaxChoices.choices,
        default=TaxChoices.INC_8,
        verbose_name="Tax Type",
    )
    is_available: models.BooleanField[bool, bool] = models.BooleanField(
        default=True, verbose_name="Available"
    )
    sort_order: models.IntegerField[int, int] = models.IntegerField(
        default=0, verbose_name="Order"
    )

    image: models.ImageField = models.ImageField(
        upload_to=menu_image_upload_to,
        validators=[validate_image_extension, validate_image_size],
        blank=True,
        null=True,
        verbose_name="Image",
        help_text=f"Formatos: {', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))}",
    )
    tags: models.ManyToManyField = models.ManyToManyField(
        ProductTag,
        related_name="products",
        blank=True,
        verbose_name="Tags (Badges)",
    )

    created_at: models.DateTimeField[Any, Any] = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField[Any, Any] = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Product"
        verbose_name_plural = "Products"
        ordering = ["category__sort_order", "sort_order", "name"]

    def __str__(self) -> str:
        return self.name

    def get_image_url(self) -> str:
        """Devuelve la URL de la imagen."""
        if not self.image:
            return ""
        return self.image.url

    def active_tags(self):
        """Tags activos ordenados."""
        return self.tags.filter(is_active=True).order_by("sort_order", "name")
