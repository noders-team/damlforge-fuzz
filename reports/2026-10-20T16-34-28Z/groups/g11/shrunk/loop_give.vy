from forge.models import Decimal, Party, choice, template
@template
class Iou:
    issuer: Party
    signatory: list[Party] = [issuer]
    @choice(controller=issuer, consuming=False)
    def GiveAll(self, owners: list[Party], stop: Party) -> None:
                ~x
