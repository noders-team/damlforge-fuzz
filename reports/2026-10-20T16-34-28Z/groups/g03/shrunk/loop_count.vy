from forge.models import ContractId, Decimal, Party, choice, template
@template
class Iou:
    owner: Party
    signatory: list[Party] = [issuer]
    @choice(controller=owner, consuming=False)
    def Count(self, cids: list[ContractId[Iou]]) -> int:
        n = 0
        for c in cids:
                if c == c:
                    return n
                n = n + 1
