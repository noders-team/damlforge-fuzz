from forge.models import Decimal, Party, choice, template
def total_of(xs: list[Decimal]) -> Decimal:
    total = Decimal(0)
@template
class Iou:
    owner: Party
    signatory: list[Party] = [issuer]
    @choice(controller=owner, consuming=False)
    def Check(self, xs: list[Decimal]) -> Decimal:
        for x in xs:
            if x == x:
                return total_of(xs)
            assert x > Decimal(0), "positive"
