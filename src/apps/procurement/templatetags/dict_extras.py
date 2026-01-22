from decimal import Decimal
from django import template

register = template.Library()

@register.filter
def get_item(d, key):
    try:
        return d.get(key)
    except Exception:
        return None

@register.filter
def mul(a, b):
    try:
        return Decimal(str(a)) * Decimal(str(b))
    except Exception:
        return None
