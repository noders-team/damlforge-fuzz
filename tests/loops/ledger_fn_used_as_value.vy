from forge.models import ContractId, Decimal, Party, choice, template, ledger_effect

@ledger_effect
def mk(issuer: Party, o: Party, a: Decimal) -> ContractId[Iou]:
    return create(Iou(issuer=issuer, owner=o, amount=a))

def pure_wrap(issuer: Party, o: Party, a: Decimal) -> ContractId[Iou]:
    return mk(issuer, o, a)

@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal
    signatory: list[Party] = [issuer]
