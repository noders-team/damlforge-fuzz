from forge.models import ContractId, Decimal, Party, choice, template, ledger_effect

@template
class Iou:
    issuer: Party
    fetch: Party
    amount: Decimal
    signatory: list[Party] = [issuer]
    observer: list[Party] = [fetch]

    @choice(controller=issuer, consuming=False)
    def Dup(self) -> ContractId[Iou]:
        return create(Iou(issuer=self.issuer, fetch=self.fetch, amount=self.amount))
