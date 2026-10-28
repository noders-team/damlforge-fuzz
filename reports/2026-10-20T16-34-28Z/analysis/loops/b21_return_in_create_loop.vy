from forge.models import ContractId, Decimal, Party, choice, template
from forge.builtins.daml_lang import create


@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal

    signatory: list[Party] = [issuer]
    observer: list[Party] = [owner]

    @choice(controller=issuer, consuming=False)
    def GiveUntil(self, owners: list[Party], stop: Party) -> None:
        for o in owners:
            if o == stop:
                return
            create(Iou(issuer=self.issuer, owner=o, amount=self.amount))
