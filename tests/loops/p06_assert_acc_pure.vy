from forge.models import ContractId, Decimal, Party, choice, template, ledger_effect

def checked_sum(xs: list[int]) -> int:
    total = 0
    for x in xs:
        assert x > 0, "positive"
        total = total + x
    return total

@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal

    signatory: list[Party] = [issuer]
    observer: list[Party] = [owner]

    @choice(controller=owner, consuming=False)
    def Noop(self) -> int:
        return checked_sum([1, 2])
