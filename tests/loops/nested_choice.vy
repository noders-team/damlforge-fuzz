from forge.models import ContractId, Decimal, Party, choice, template, ledger_effect


@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal

    signatory: list[Party] = [issuer]
    observer: list[Party] = [owner]

    @choice(controller=owner, consuming=False)
    def Give(self, groups: list[list[Party]], stop: Party) -> None:
        for g in groups:
            for o in g:
                if o == stop:
                    return
                create(Iou(issuer=self.issuer, owner=o, amount=self.amount))
