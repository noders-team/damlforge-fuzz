from forge.models import ContractId, Decimal, Party, choice, template, ledger_effect

@ledger_effect
def make(issuer: Party, o: Party, a: Decimal) -> ContractId[Iou]:
    return create(Iou(issuer=issuer, owner=o, amount=a))

@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal

    signatory: list[Party] = [issuer]
    observer: list[Party] = [owner]

    @choice(controller=owner, consuming=False)
    def Many(self, owners: list[Party]) -> int:
        n = 0
        for o in owners:
            make(self.issuer, o, self.amount)
            n = n + 1
        return n
