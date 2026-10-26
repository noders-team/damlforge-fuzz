from forge.models import ContractId, Decimal, Party, choice, template
import models as M


@template
class Desk:
    issuer: Party
    owner: Party

    signatory: list[Party] = [issuer]
    observer: list[Party] = [owner]

    @choice(controller=issuer, consuming=False)
    def Issue(self, amount: Decimal) -> ContractId[M.Note]:
        lot = M.cash_lot(M.double(amount))
        return create(M.Note(str=self.issuer, owner=self.owner, lot=lot))

    @choice(controller=owner, consuming=False)
    def Size(self, cid: ContractId[M.Note]) -> Decimal:
        note = fetch(cid)
        return note.date(2020, 13, 40).amount
