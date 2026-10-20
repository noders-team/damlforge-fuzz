from forge.models import ContractId, Decimal, Party, choice, template


@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal

    signatory: list[Party] = [issuer]
    observer: list[Party] = [owner]

    @choice(controller=owner, consuming=False)
    def Count(self, cids: list[ContractId[float]]) -> int:
        n = 0
        for c in cids:
            i = fetch(c)
            if i.amount > Decimal(1):
                n = n + 1
        return n
