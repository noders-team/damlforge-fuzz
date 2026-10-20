from forge.models import ContractId, Decimal, Party, choice, template, ledger_effect

struct Terms:
    amount: Decimal

def has(ps: list[Party], p: Party) -> bool:
    for q in ps:
        if q == p:
            return True
    return False

@template
class Iou:
    issuer: Party
    owner: Party
    terms: Terms
    signatory: list[Party] = [issuer]
