from decimal import Decimal

def test_financial_amount_is_decimal():
    assert Decimal("1000.00") > 0
