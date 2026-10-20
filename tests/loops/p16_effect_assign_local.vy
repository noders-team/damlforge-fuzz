from forge.models import ContractId, Decimal, Party, choice, template, ledger_effect

@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal

    signatory: list[Party] = [issuer]
    observer: list[Party] = [owner]

    @choice(controller=owner, consuming=False)
    def M(self, owners: list[Party]) -> bool:
        for o in owners:
            cid = create(Iou(issuer=self.issuer, owner=o, amount=self.amount))
        return True
