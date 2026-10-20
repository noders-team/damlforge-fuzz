from forge.models import ContractId, Decimal, Party, choice, template, ledger_effect

@ledger_effect
def first_big(cids: list[ContractId[Iou]]) -> Decimal:
    for c in cids:
        i = fetch(c)
        if i.amount > Decimal(1):
            return i.amount
    return Decimal(0)

@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal
    signatory: list[Party] = [issuer]
