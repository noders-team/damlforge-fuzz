from forge.models import ContractId, Decimal, Party, choice, template, ledger_effect

@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal

    signatory: list[Party] = [issuer]
    observer: list[Party] = [owner]

    @choice(controller=owner, consuming=False)
    def Sum(self, xs: list[Decimal]) -> Decimal:
        total = Decimal(0)
        for x in xs:
            total = total + x
        return total
