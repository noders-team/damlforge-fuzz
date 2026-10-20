from forge.models import ContractId, Decimal, Party, choice, template, ledger_effect

def has(ps: list[Party], p: Party) -> bool:
    for q in ps:
        if q == p:
            pass
        else:
            return False
    return True

@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal
    signatory: list[Party] = [issuer]
