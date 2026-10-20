from forge.models import ContractId, Decimal, Party, choice, template


@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal

    signatory: list[Party] = [issuer]

    @choice(controller=owner, consuming=False)
    def Count(self, cids: list[ContractId[Iou]]) -> int:
        n = 0
        for c in cids:
            i = fetch(c)
            if i.amount > Decimal(1):
                if c == c:
                    return n
                n = n + 1
        return n
