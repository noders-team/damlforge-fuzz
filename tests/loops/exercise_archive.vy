from forge.models import ContractId, Decimal, Party, choice, template, ledger_effect

@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal
    signatory: list[Party] = [issuer]

    @choice(controller=owner, consuming=False)
    def Bye(self, cids: list[ContractId[Iou]]) -> bool:
        for c in cids:
            archive(c)
        return True
