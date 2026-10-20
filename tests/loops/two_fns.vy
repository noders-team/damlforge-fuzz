from forge.models import ContractId, Decimal, Party, choice, template, ledger_effect


def has_party(ps: list[Party], p: Party) -> bool:
    for q in ps:
        if q == p:
            return True
    return False

@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal

    signatory: list[Party] = [issuer]
    observer: list[Party] = [owner]

    @choice(controller=owner, consuming=False)
    def GiveUntil(self, owners: list[Party], stop: Party) -> None:
        for o in owners:
            if o == stop:
                return
            create(Iou(issuer=self.issuer, owner=o, amount=self.amount))
