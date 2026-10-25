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


class OptionGroup(models.Model):
    class SelectionType(models.TextChoices):
        SINGLE = "single", "Selección única"
        MULTIPLE = "multiple", "Selección múltiple"

    id: models.UUIDField[uuid.UUID, uuid.UUID] = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    name: models.CharField[str, str] = models.CharField(
        max_length=150, unique=True, verbose_name="Name"
    )
    description: models.TextField[str | None, str | None] = models.TextField(
        blank=True, verbose_name="Description"
    )
    selection_type: models.CharField[str, str] = models.CharField(
        max_length=10,
        choices=SelectionType.choices,
        default=SelectionType.SINGLE,
        verbose_name="Selection Type",
    )
    min_selections: models.PositiveSmallIntegerField[int, int] = (
        models.PositiveSmallIntegerField(default=1, verbose_name="Min selections")
    )
    max_selections: models.PositiveSmallIntegerField[int, int] = (
        models.PositiveSmallIntegerField(default=1, verbose_name="Max selections")
    )
    is_active: models.BooleanField[bool, bool] = models.BooleanField(
        default=True, verbose_name="Active"
    )
    created_at: models.DateTimeField[Any, Any] = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField[Any, Any] = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Option Group"
        verbose_name_plural = "Option Groups"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def clean(self) -> None:
        if self.max_selections < self.min_selections:
            raise ValidationError(
                "Max selections no puede ser menor que min selections."
            )

        if self.selection_type == OptionGroup.SelectionType.SINGLE:
            if self.min_selections > 1 or self.max_selections > 1:
                raise ValidationError(
                    "Un grupo de selección única debe tener mínimo y máximo 1."
                )


class OptionValue(models.Model):
    id: models.UUIDField[uuid.UUID, uuid.UUID] = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    group: models.ForeignKey[OptionGroup, OptionGroup] = models.ForeignKey(
        OptionGroup,
        on_delete=models.CASCADE,
        related_name="values",
        verbose_name="Option group",
    )
    name: models.CharField[str, str] = models.CharField(
        max_length=150, verbose_name="Name"
    )
    price_delta: models.DecimalField[Decimal, Decimal] = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Price delta",
    )
    is_available: models.BooleanField[bool, bool] = models.BooleanField(
        default=True, verbose_name="Available"
    )
    sort_order: models.IntegerField[int, int] = models.IntegerField(
        default=0, verbose_name="Order"
    )
    created_at: models.DateTimeField[Any, Any] = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField[Any, Any] = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Option Value"
        verbose_name_plural = "Option Values"
        ordering = ["group", "sort_order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["group", "name"],
                name="uniq_option_value_per_group",
            )
        ]

    def __str__(self) -> str:
        return f"{self.group.name}: {self.name}"


class ProductOptionGroup(models.Model):
    id: models.UUIDField[uuid.UUID, uuid.UUID] = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    product: models.ForeignKey[Product, Product] = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="option_attachments",
        verbose_name="Product",
    )
    option_group: models.ForeignKey[OptionGroup, OptionGroup] = models.ForeignKey(
        OptionGroup,
        on_delete=models.CASCADE,
        related_name="product_attachments",
        verbose_name="Option group",
    )
    is_required: models.BooleanField[bool, bool] = models.BooleanField(
        default=False, verbose_name="Required"
    )
    sort_order: models.IntegerField[int, int] = models.IntegerField(
        default=0, verbose_name="Order"
    )
    condition_parent: models.ForeignKey[
        ProductOptionGroup | None,
        ProductOptionGroup | None,
    ] = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="conditional_children",
        verbose_name="Visible if parent option selected",
    )
    condition_values: models.ManyToManyField[OptionValue, Any] = models.ManyToManyField(
        OptionValue,
        blank=True,
        related_name="condition_attachments",
        verbose_name="Condition values",
    )
    created_at: models.DateTimeField[Any, Any] = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField[Any, Any] = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Product Option Group"
        verbose_name_plural = "Product Option Groups"
        ordering = ["sort_order", "option_group__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "option_group"],
                name="uniq_product_option_group",
            )
        ]

    def __str__(self) -> str:
        return f"{self.product.name} → {self.option_group.name}"

    def clean(self) -> None:
        if self.condition_parent is not None:
            if self.condition_parent.product_id != self.product_id:
                raise ValidationError(
                    "La condición debe apuntar a un grupo del mismo producto."
                )

            if self.condition_parent_id == self.pk:
                raise ValidationError("Un grupo no puede depender de sí mismo.")


class CategoryAvailabilityRule(models.Model):
    id: models.UUIDField[uuid.UUID, uuid.UUID] = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    category: models.ForeignKey[Category, Category] = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="availability_rules",
        verbose_name="Category",
    )
    name: models.CharField[str, str] = models.CharField(
        max_length=120, verbose_name="Name"
    )
    is_active: models.BooleanField[bool, bool] = models.BooleanField(
        default=True, verbose_name="Active"
    )
    start_date: models.DateField[Any, Any] = models.DateField(
        null=True, blank=True, verbose_name="Start date"
    )
    end_date: models.DateField[Any, Any] = models.DateField(
        null=True, blank=True, verbose_name="End date"
    )
    start_time: models.TimeField[Any, Any] = models.TimeField(
        null=True, blank=True, verbose_name="Start time"
    )
    end_time: models.TimeField[Any, Any] = models.TimeField(
        null=True, blank=True, verbose_name="End time"
    )
    monday: models.BooleanField[bool, bool] = models.BooleanField(default=False)
    tuesday: models.BooleanField[bool, bool] = models.BooleanField(default=False)
    wednesday: models.BooleanField[bool, bool] = models.BooleanField(default=False)
    thursday: models.BooleanField[bool, bool] = models.BooleanField(default=False)
    friday: models.BooleanField[bool, bool] = models.BooleanField(default=False)
    saturday: models.BooleanField[bool, bool] = models.BooleanField(default=False)
    sunday: models.BooleanField[bool, bool] = models.BooleanField(default=False)
    badge_text: models.CharField[str, str] = models.CharField(
        max_length=80, blank=True, verbose_name="Badge text"
    )
    sort_order: models.IntegerField[int, int] = models.IntegerField(
        default=0, verbose_name="Order"
    )
    created_at: models.DateTimeField[Any, Any] = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField[Any, Any] = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Category Availability Rule"
        verbose_name_plural = "Category Availability Rules"
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return f"{self.category.name}: {self.name}"
