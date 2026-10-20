from forge.models import ContractId, Decimal, Party, choice, template, ledger_effect

def f(xs: list[int]) -> int:
    for x in xs:
        y = x + 1
    return 0

@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal
    signatory: list[Party] = [issuer]
