from forge.models import ContractId, Decimal, Party, choice, template, ledger_effect

@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal
    signatory: list[Party] = [issuer]

    def has(self, ps: list[Party]) -> bool:
        for q in ps:
            if q == self.owner:
                return True
        return False

    @choice(controller=owner, consuming=False)
    def Has(self, ps: list[Party]) -> bool:
        return self.has(ps)
