from forge.models import ContractId, Decimal, Party, choice, ledger_effect, template
def verify(cids: list[ContractId[Iou]], p: Party) -> Decimal:
    owner: Party
@template
class Iou:
    signatory: list[Party] = [issuer]
