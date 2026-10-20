from forge.models import Decimal, Party, choice, template


@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal

    signatory: list[Party] = [issuer]
    observer: list[Party] = [owner]

    @choice(controller=owner, consuming=False)
    def Fee(self) -> Decimal:
        return self.amount / Decimal(100)

    def Fee(self) -> Decimal:
        return self.amount / Decimal(50)
