from forge.models import ContractId, Decimal, Party, choice, template, ledger_effect

def f(cids: list[ContractId[Iou]]) -> int:
    for c in cids:
        fetch(c)
    return 0

@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal
    signatory: list[Party] = [issuer]
