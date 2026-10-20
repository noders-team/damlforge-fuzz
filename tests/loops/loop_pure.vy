from forge.models import Decimal, Party, choice, template


def total_of(xs: list[Decimal]) -> Decimal:
    total = Decimal(0)
    for x in xs:
        if x > Decimal(0):
            total = total + x
    return total


def grid_sum(rows: list[list[int]]) -> int:
    total = 0
    for row in rows:
        for x in row:
            total = total + x
    return total


def has_party(ps: list[Party], p: Party) -> bool:
    for q in ps:
        if q == p:
            return True
    return False


@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal

    signatory: list[Party] = [issuer]
    observer: list[Party] = [owner]

    @choice(controller=owner, consuming=False)
    def Check(self, xs: list[Decimal]) -> Decimal:
        for x in xs:
            assert x > Decimal(0), "positive"
        return total_of(xs)
