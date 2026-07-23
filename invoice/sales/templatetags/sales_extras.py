from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter
def money(value):
    """Format an amount with 3 decimals (millimes), but drop the decimals
    entirely when the value is a whole number.

    Examples:
        1543.000 -> "1543"
        1543.500 -> "1543.500"
        1543.750 -> "1543.750"
    """
    if value is None or value == '':
        return value
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return value
    if d == d.to_integral_value():
        return str(int(d))
    return str(d.quantize(Decimal('0.001')))
