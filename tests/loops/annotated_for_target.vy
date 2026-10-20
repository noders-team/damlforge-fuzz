from forge.models import ContractId, Decimal, Party, choice, template, ledger_effect

def f(xs: list[int]) -> int:
    n = 0
    for x: int in xs:
        n = n + x
    return n

@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal
    signatory: list[Party] = [issuer]
