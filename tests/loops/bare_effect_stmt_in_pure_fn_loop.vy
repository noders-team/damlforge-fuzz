from forge.models import ContractId, Decimal, Party, choice, template, ledger_effect

def f(cids: list[ContractId[Iou]]) -> int:
    n = 0
    for c in cids:
        fetch(c)
        n = n + 1
    return n

@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal
    signatory: list[Party] = [issuer]
