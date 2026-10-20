from forge.models import Decimal, Party, choice, template


@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal

    signatory: list[Party] = [issuer]
    observer: list[Party] = [owner]

    def fee(self) -> Decimal:
        return self.amount / Decimal(100)

    @choice(controller=owner, consuming=False)
    def Fee(self) -> Decimal:
        return self.fee()
