from forge.models import ContractId, Decimal, Party, choice, template, ledger_effect

def find(groups: list[list[Party]], p: Party) -> bool:
    for g in groups:
        for o in g:
            if o == p:
                return True
    return False

@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal
    signatory: list[Party] = [issuer]
