from forge.models import Decimal, Party, choice, template


def under_limit(xs: list[Decimal], limit: Decimal) -> bool:
    for x in xs:
        if x > Decimal(0):
            assert x <= limit, "over the limit"
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
        return under_limit(xs, self.amount)
