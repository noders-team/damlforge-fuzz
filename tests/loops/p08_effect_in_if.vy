from forge.models import ContractId, Decimal, Party, choice, template, ledger_effect

@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal

    signatory: list[Party] = [issuer]
    observer: list[Party] = [owner]

    @choice(controller=owner, consuming=False)
    def Pick(self, owners: list[Party]) -> int:
        n = 0
        for o in owners:
            if o != self.owner:
                create(Iou(issuer=self.issuer, owner=o, amount=self.amount))
                n = n + 1
        return n
