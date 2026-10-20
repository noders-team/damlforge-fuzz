from forge.models import ContractId, Decimal, Party, choice, template


@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal

    signatory: list[Party] = [issuer]
    observer: list[Party] = [owner]

    @choice(controller=owner, consuming=False)
    def Total(self, cids: list[ContractId[Iou]]) -> Decimal:
        total = Decimal(0)
        for c in cids:
            total = total + fetch(c).amount
        return total
