from forge.models import ContractId, Decimal, Party, choice, template, ledger_effect

@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal

    signatory: list[Party] = [issuer]
    observer: list[Party] = [owner]

    @choice(controller=owner, consuming=True)
    def Bump(self, xs: list[Decimal]) -> ContractId[Iou]:
        for x in xs:
            self.amount = self.amount + x
        return create(Iou(issuer=self.issuer, owner=self.owner, amount=self.amount))
