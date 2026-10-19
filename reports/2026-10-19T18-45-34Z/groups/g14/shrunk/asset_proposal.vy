from forge.models import ContractId, Party, choice, template
@template
class Asset:
    owner: Party
    signatory: list[Party] = [issuer, owner]
    @choice(controller=owner, consuming=True)
    def Reject(self) -> None:
        ~x
