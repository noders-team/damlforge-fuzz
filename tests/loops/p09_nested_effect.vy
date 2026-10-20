from forge.models import ContractId, Decimal, Party, choice, template, ledger_effect

@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal

    signatory: list[Party] = [issuer]
    observer: list[Party] = [owner]

    @choice(controller=owner, consuming=False)
    def Grid(self, groups: list[list[Party]]) -> int:
        n = 0
        for g in groups:
            for o in g:
                create(Iou(issuer=self.issuer, owner=o, amount=self.amount))
                n = n + 1
        return n
