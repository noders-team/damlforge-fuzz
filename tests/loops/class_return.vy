from forge.models import ContractId, Decimal, Party, choice, template, ledger_effect


@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal

    signatory: list[Party] = [issuer]
    observer: list[Party] = [owner]
    return

    @choice(controller=owner, consuming=False)
    def Find(self, ps: list[Party]) -> bool:
        for q in ps:
            if q == self.owner:
                return True
        return False
