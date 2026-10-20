from forge.models import ContractId, Decimal, Party, choice, template, ledger_effect

@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal
    signatory: list[Party] = [issuer]

    @choice(controller=owner, consuming=False)
    def A(self, c: ContractId[Iou]) -> bool:
        assert fetch(c).amount > Decimal(0), "pos"
        return True
