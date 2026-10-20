from forge.models import ContractId, Decimal, Party, choice, template



@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal

    signatory: list[Party] = [issuer]
    observer: list[Party] = [owner]

    @choice(controller=owner, consuming=False)
    def Many(self, owners: list[Party]) -> list[ContractId[Iou]]:
        for _k in range(0, 2):
            cids: list[ContractId[Iou]] = []
        for Iou in owners:
            if o != self.owner:
                cid = create(Iou(issuer=self.issuer, owner=o, amount=self.amount))
                cids.append(cid)
        return cids
