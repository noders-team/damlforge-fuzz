from forge.models import ContractId, Decimal, Party, choice, template, ledger_effect


def has_party(ps: list[Party], p: Party) -> bool:
    for q: Party in ps:
        if q == p:
            return True
    return False

@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal

    signatory: list[Party] = [issuer]
    observer: list[Party] = [owner]
