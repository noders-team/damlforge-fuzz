from forge.models import ContractId, Decimal, Party, choice, template
from forge.builtins.daml_lang import fetch


def total_of(cids: list[ContractId[Iou]]) -> Decimal:
    total = Decimal(0)
    for c in cids:
        i = fetch(c)
        total = total + i.amount
    return total


@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal

    signatory: list[Party] = [issuer]
    observer: list[Party] = [owner]

    @choice(controller=owner, consuming=False)
    def Total(self, cids: list[ContractId[Iou]]) -> Decimal:
        return total_of(cids)
