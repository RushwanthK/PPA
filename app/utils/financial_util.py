from decimal import Decimal, ROUND_HALF_UP

def money(value):
    if value is None:
        return 0.0

    return float(
        Decimal(str(value)).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )
    )
