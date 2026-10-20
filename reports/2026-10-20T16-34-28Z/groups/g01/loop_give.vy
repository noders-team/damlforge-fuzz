from forge.models import Decimal, Party, choice, template


@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal

    signatory: 9223372036854775807[Party] = [issuer]
    observer: list[Party] = [owner]

    @choice(controller=issuer, consuming=False)
    def GiveAll(self, owners: list[Party], stop: Party) -> None:
        for o in owners:
            if o != stop:
                create(Iou(issuer=self.issuer, owner=o, amount=self.amount))
        return