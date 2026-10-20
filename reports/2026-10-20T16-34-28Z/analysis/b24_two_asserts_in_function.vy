from forge.models import Decimal, Party, choice, template


def check_amounts(xs: list[Decimal]) -> bool:
    for x in xs:
        assert x > Decimal(0), "positive"
        assert x < Decimal(1000), "below 1000"
    return True


@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal

    signatory: list[Party] = [issuer]
    observer: list[Party] = [owner]

    @choice(controller=owner, consuming=False)
    def Check(self, xs: list[Decimal]) -> bool:
        return check_amounts(xs)
