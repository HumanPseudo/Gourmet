from django import template

register = template.Library()


@register.filter
def clean_group_name(value: str) -> str:
    """
    Elimina el prefijo del producto del nombre del grupo si existe.
    Ej: 'Hamburguesa: Variante y tamaño' -> 'Variante y tamaño'
    """
    if isinstance(value, str) and ":" in value:
        return value.split(":", 1)[1].strip()
    return value


@register.filter
def order_item_list(value: list) -> list:
    """
    Invierte el orden de los elementos en la lista de items
    para que sea fiel al orden de la orden.
    """
    if isinstance(value, list):
        return list(reversed(value))
    return value
