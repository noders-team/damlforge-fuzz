from forge.models import ContractId, Decimal, Party, choice, template
from forge.builtins.daml_lang import fetch


@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal

    signatory: list[Party] = [issuer]
    observer: list[Party] = [owner]

    @choice(controller=owner, consuming=False)
    def CountLarger(self, cids: list[ContractId[Iou]]) -> int:
        n = 0
        for c in cids:
            if fetch(c).amount > self.amount:
                n = n + 1
        return n
