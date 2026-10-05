from django.contrib import admin
from django.utils.html import format_html

from .models import Category, Product, ProductTag


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin[Category]):
    list_display = ("name", "sort_order", "is_active", "products_count")
    list_editable = ("sort_order", "is_active")
    search_fields = ("name",)

    @admin.display(description="# Productos", ordering="products__count")
    def products_count(self, obj: Category) -> int:
        return obj.products.count()


@admin.register(ProductTag)
class ProductTagAdmin(admin.ModelAdmin[ProductTag]):
    list_display = ("icon_preview", "name", "slug", "color", "sort_order", "is_active")
    list_editable = ("sort_order", "is_active", "color")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("icon_preview_large",)
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "name",
                    "slug",
                    "description",
                    "icon",
                    "icon_preview_large",
                    "color",
                    "sort_order",
                    "is_active",
                )
            },
        ),
    )

    @admin.display(description="Preview")
    def icon_preview(self, obj: ProductTag) -> str:
        if not obj.icon:
            return "—"
        return format_html(
            '<img src="{}" style="height:24px;width:24px;" alt="{}">',
            obj.icon.url,
            obj.name,
        )

    @admin.display(description="Preview grande")
    def icon_preview_large(self, obj: ProductTag) -> str:
        if not obj.icon:
            return "Sube un SVG para ver el preview"
        return format_html(
            '<img src="{}" style="height:48px;width:48px;" alt="{}">',
            obj.icon.url,
            obj.name,
        )


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin[Product]):
    list_display = (
        "image_thumb",
        "name",
        "category",
        "price",
        "is_available",
        "tags_list",
        "sort_order",
    )
    list_display_links = ("name",)  # <-- AGREGAR: Hace que el nombre sea clickeable
    list_editable = ("price", "is_available", "sort_order")
    list_filter = ("category", "is_available", "tags")
    search_fields = ("name", "description")
    filter_horizontal = ("tags",)
    readonly_fields = ("image_preview",)
    fieldsets = (
        (
            "Información básica",
            {
                "fields": (
                    "name",
                    "category",
                    "description",
                    "price",
                    "tax_type",
                    "is_available",
                    "sort_order",
                )
            },
        ),
        (
            "Imagen",
            {
                "fields": ("image", "image_preview"),
                "description": (
                    "Formatos permitidos: .jpg, .jpeg, .png, .webp, .jfif. "
                    "Tamaño máximo recomendado: 2 MB."
                ),
            },
        ),
        (
            "Badges / Etiquetas",
            {
                "fields": ("tags",),
                "description": (
                    "Mantén presionado Ctrl (o Cmd en Mac) para "
                    "seleccionar múltiples badges."
                ),
            },
        ),
    )

    @admin.display(description="Img")
    def image_thumb(self, obj: Product) -> str:
        if not obj.image:
            return "—"
        return format_html(
            '<img src="{}" style="height:40px;width:40px;object-fit:cover;'
            'border-radius:4px;" alt="{}">',
            obj.get_image_url(),
            obj.name,
        )

    @admin.display(description="Preview")
    def image_preview(self, obj: Product) -> str:
        if not obj.image:
            return "Sin imagen"
        return format_html(
            '<img src="{}" style="max-width:300px;max-height:300px;'
            'border-radius:8px;" alt="{}">',
            obj.get_image_url(),
            obj.name,
        )

    @admin.display(description="Badges")
    def tags_list(self, obj: Product) -> str:
        tags = obj.active_tags()
        if not tags:
            return "—"
        return ", ".join(t.name for t in tags)
