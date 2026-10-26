from enum import Enum, auto

from forge.models import Decimal, Party, template


class Kind(Enum):
    CASH = auto()
    BOND = auto()


@template
class Note:
    owner: Party
    kind: Kind
    amount: Decimal

    signatory: list[Party] = [owner]


def double(x: Decimal) -> Decimal:
    return x + x
