from forge.models import ContractId, Decimal, Party, choice, template
@template
class Iou:
    owner: Party
    signatory: list[Party] = [issuer]
    @choice(controller=owner, consuming=False)
    def Count(self, cids: list[ContractId[Iou]]) -> int:
            if fetch(c).amount > Decimal(1):
                n = n + 1
