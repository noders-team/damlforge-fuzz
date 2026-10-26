from forge.models import Decimal


def double(x: Decimal) -> Decimal:
    return x + x


def fee(x: Decimal, rate: Decimal) -> Decimal:
    return x * rate
