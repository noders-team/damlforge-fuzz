from forge.models import ContractId, Party, choice, template


@template
class Asset:
    issuer: Party
    owner: Party
    name: str

    signatory: list[Party] = [issuer, owner]

    # The new owner must sign the asset too, so giving it makes a proposal.
    @choice(controller=owner, consuming=True)
    def Give(self, new_owner: Party) -> ContractId[AssetProposal]:
        assert new_owner != self.owner, "cannot give an asset to its current owner"
        return create(AssetProposal(issuer=self.issuer, owner=new_owner, name=self.name))


@template
class AssetProposal:
    issuer: Party
    owner: Party
    name: str

    signatory: list[Party] = [issuer]
    observer: list[Party] = [owner]

    @choice(controller=owner, consuming=True)
    def Accept(self) -> ContractId[Asset]:
        return create(Asset(issuer=self.issuer, owner=self.owner, name=self.name))

    @choice(controller=owner, consuming=True)
    def Reject(self) -> None:
        return
