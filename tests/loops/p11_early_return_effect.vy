from forge.models import ContractId, Decimal, Party, choice, template, ledger_effect

@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal

    signatory: list[Party] = [issuer]
    observer: list[Party] = [owner]

    @choice(controller=owner, consuming=False)
    def FindBig(self, cids: list[ContractId[Iou]]) -> Decimal:
        for c in cids:
            i = fetch(c)
            if i.amount > Decimal(100):
                return i.amount
        return Decimal(0)
