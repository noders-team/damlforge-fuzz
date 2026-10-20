from forge.models import ContractId, Decimal, Party, choice, template, ledger_effect

@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal

    signatory: list[Party] = [issuer]
    observer: list[Party] = [owner]

    @choice(controller=owner, consuming=False)
    def C(self, cids: list[ContractId[Iou]]) -> int:
        n = 0
        for c in cids:
            if fetch(c).amount > Decimal(1):
                n = n + 1
        return n
