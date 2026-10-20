from forge.models import Decimal, Party, choice, template


def first_positive(rows: list[list[int]]) -> int:
    for row in rows:
        for x in row:
            if x > 0:
                return x
    return 0


@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal

    signatory: list[Party] = [issuer]
    observer: list[Party] = [owner]

    @choice(controller=owner, consuming=False)
    def FirstPositive(self, rows: list[list[int]]) -> int:
        return first_positive(rows)
