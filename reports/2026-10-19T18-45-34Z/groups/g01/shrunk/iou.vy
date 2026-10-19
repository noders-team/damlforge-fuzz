from forge.models import ContractId, Decimal, Party, choice, template
@template
class Iou:
    owner: Party
    signatory: list[Party] = [issuer]
    @choice(controller=owner, consuming=True)
    def Transfer(self, new_owner: Party) -> ContractId[Iou]:
        import os
