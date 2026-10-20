from forge.models import Decimal, Party, template


@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal

    signatory: list[Party] = [issuer]
    observer: list[Party] = [owner]
    ensure: bool = amount > Decimal(0)
    ensure: bool = amount < Decimal(1000)
