from forge.models import Decimal, Party, choice, template


@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal

    signatory: list[Party] = [issuer]
    observer: list[Party] = [owner]

    @choice(controller=owner, consuming=False)
    def Check(self, xs: list[Decimal]) -> None:
        for x in xs:
            pass
            assert x > Decimal(0), "positive"
