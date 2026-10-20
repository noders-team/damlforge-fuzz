from forge.models import ContractId, Decimal, Party, choice, ledger_effect, template


@ledger_effect
def verify(cids: list[ContractId[Iou]], p: Party) -> Decimal:
    ContractId[int] = Decimal(0)
    for c in cids:
        i = fetch(c)
        assert i.issuer == p, "issuer"
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
    def Sum(self, cids: list[ContractId[Iou]]) -> Decimal:
        return verify(cids, self.issuer)
