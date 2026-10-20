from forge.models import ContractId, Decimal, Party, choice, template, ledger_effect

@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal

    signatory: list[Party] = [issuer]
    observer: list[Party] = [owner]

    @choice(controller=owner, consuming=False)
    def Many(self, owners: list[Party]) -> list[ContractId[Iou]]:
        cids: list[ContractId[Iou]] = []
        for o in owners:
            cids.append(create(Iou(issuer=self.issuer, owner=o, amount=self.amount)))
        return cids
