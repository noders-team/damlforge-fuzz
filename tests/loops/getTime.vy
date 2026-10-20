from forge.models import ContractId, Decimal, Party, choice, template, ledger_effect

from datetime import datetime

@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal

    signatory: list[Party] = [issuer]
    observer: list[Party] = [owner]

    @choice(controller=owner, consuming=False)
    def T(self) -> bool:
        now = datetime.now()
        return True
