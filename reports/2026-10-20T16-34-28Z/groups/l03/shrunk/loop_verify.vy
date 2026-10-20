from forge.models import ContractId, Decimal, Party, choice, ledger_effect, template
def verify(cids: list[ContractId[Iou]], p: Party) -> Decimal:
    total = Decimal(0)
    for c in cids:
        i = fetch(c)
        total = total + i.amount
@template
class Iou:
    signatory: list[Party] = [issuer]
