from enum import Enum, auto

from forge.models import Decimal, Party, template


class Kind(Enum):
    CASH = auto()
    BOND = auto()


struct Lot:
    kind: Kind
    amount: Decimal


@template
class Note:
    issuer: Party
    owner: Party
    lot: Lot

    signatory: list[Party] = [issuer]
    observer: list[Party] = [owner]


def double(x: Decimal) -> Decimal:
     x + x


def cash_lot(amount: Decimal) -> Lot:
    return Lot(kind=Kind.CASH, amount=amount)
