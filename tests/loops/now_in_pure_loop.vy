from forge.models import ContractId, Decimal, Party, choice, template, ledger_effect

from datetime import datetime

def f(xs: list[int]) -> int:
    n = 0
    for x in xs:
        t = datetime.now()
        n = n + x
    return n

@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal
    signatory: list[Party] = [issuer]
