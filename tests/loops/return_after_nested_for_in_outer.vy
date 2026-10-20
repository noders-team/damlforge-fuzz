from forge.models import ContractId, Decimal, Party, choice, template, ledger_effect

def f(groups: list[list[int]]) -> int:
    for g in groups:
        for x in g:
            pass
        return 1
    return 0

@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal
    signatory: list[Party] = [issuer]
