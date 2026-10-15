from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal, localcontext


def decimal_value(value: Decimal | float | int) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def line_amount(quantity: int, price: Decimal) -> Decimal:
    price = decimal_value(price)
    with localcontext() as context:
        context.prec = max(
            28, len(price.as_tuple().digits) + len(str(quantity)) + max(int(price.as_tuple().exponent), 0) + 4
        )
        return (quantity * price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def commission_amount(turnover: Decimal, percent: Decimal) -> Decimal:
    with localcontext() as context:
        context.prec = max(28, len(turnover.as_tuple().digits) + len(percent.as_tuple().digits) + 2)
        return turnover * percent / 100


def sum_amounts(values: Iterable[Decimal]) -> Decimal:
    amounts = list(values)
    if not amounts:
        return Decimal(0)
    integer_digits = max(max(value.adjusted() + 1, 1) for value in amounts)
    fraction_digits = max(max(-int(value.as_tuple().exponent), 0) for value in amounts)
    with localcontext() as context:
        context.prec = max(28, integer_digits + fraction_digits + len(str(len(amounts))) + 2)
        return sum(amounts, Decimal(0))
