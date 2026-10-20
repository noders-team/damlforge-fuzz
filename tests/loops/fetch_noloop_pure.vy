from forge.models import ContractId, Decimal, Party, choice, template, ledger_effect


def amount_of(c: ContractId[Iou]) -> Decimal:
    return fetch(c).amount

@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal

    signatory: list[Party] = [issuer]
    observer: list[Party] = [owner]
