from forge.models import ContractId, Decimal, Party, choice, template, ledger_effect


def first_pos(xss: list[list[int]]) -> int:
    for xs in xss:
        for x in xs:
            if x > 0:
                return x
    return 0

@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal

    signatory: list[Party] = [issuer]
    observer: list[Party] = [owner]
