from forge.models import ContractId, Decimal, Party, choice, template, ledger_effect

@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal
    signatory: list[Party] = [issuer]

    @choice(controller=owner, consuming=False)
    def B(self, c: ContractId[Iou]) -> int:
        n = 0
        for p in [fetch(c).owner]:
            n = n + 1
        return n
