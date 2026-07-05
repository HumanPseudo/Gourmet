from decimal import ROUND_HALF_UP, Decimal

from django import template
from django.template.defaultfilters import stringfilter

register = template.Library()


@register.filter
@stringfilter
def peso(value: str) -> str:
    try:
        d = Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        parts = f"{d:,.2f}".split(".")
        int_part = parts[0].replace(",", ".")
        return f"$ {int_part},{parts[1]}"
    except (ValueError, TypeError):
        return value


@register.filter
def multiply(value: Decimal, arg: Decimal) -> str:
    try:
        return str(value * arg)
    except (ValueError, TypeError):
        return "0"
