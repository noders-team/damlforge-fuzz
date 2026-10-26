from forge.models import ContractId, Decimal, Party, choice, template
from models import Kind, Lot, Note, double


@template
class Desk:
    issuer: Party
    owner: Party

    signatory: list[Party] = [issuer]
    observer: list[Party] = [owner]

    @choice(controller=issuer, consuming=False)
    def Issue(self, amount: Decimal) -> ContractId[Note]:
        lot = Lot(kind=Kind.CASH, amount=double(amount))
        return create(Note(issuer=self.issuer, owner=self.owner, lot=lot))

    @choice(controller=owner, consuming=False)
    def Size(self, cid: ContractId[TextMap[str]]) -> Decimal:
        note = fetch(cid)
        return fetch(cid).lot.amount
