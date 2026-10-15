from decimal import Decimal

from src.common.domain.money import commission_amount, line_amount, sum_amounts


def test_financial_values_keep_precision_beyond_default_decimal_context() -> None:
    turnover = Decimal("100000000000000000000000000.01")
    assert sum_amounts([turnover, Decimal("0.01")]) == Decimal("100000000000000000000000000.02")
    assert commission_amount(turnover, Decimal("0.0001")) == Decimal("100000000000000000000.00000001")
    assert line_amount(3, Decimal("0.335")) == Decimal("1.01")
    assert line_amount(1, Decimal("1E+30")) == Decimal("1000000000000000000000000000000.00")
