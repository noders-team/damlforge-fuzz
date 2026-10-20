from forge.models import Decimal, Party, choice, template


@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal

    signatory: list[Party] = [issuer]
    observer: list[Party] = [owner]

    @choice(controller=owner, consuming=False)
    def FirstLarge(self, xs: list[Decimal]) -> Decimal:
        for x in xs:
            assert x > Decimal(0), "positive"
            if x > self.amount:
                return x
        return Decimal(0)
