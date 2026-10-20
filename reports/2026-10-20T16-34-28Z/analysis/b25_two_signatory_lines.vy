from forge.models import Decimal, Party, choice, template


@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal

    signatory: list[Party] = [issuer]
    observer: list[Party] = [owner]
    signatory: list[Party] = [issuer, owner]

    @choice(controller=issuer, consuming=False)
    def Give(self, new_owner: Party) -> None:
        create(Iou(issuer=self.issuer, owner=new_owner, amount=self.amount))
