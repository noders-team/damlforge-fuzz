from forge.models import ContractId, Decimal, Party, choice, template, ledger_effect

@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal
    signatory: list[Party] = [issuer]

    @choice(controller=owner, consuming=False)
    def Find(self, groups: list[list[Party]]) -> bool:
        for g in groups:
            create(Iou(issuer=self.issuer, owner=self.owner, amount=self.amount))
            for o in g:
                if o == self.owner:
                    return True
        return False
