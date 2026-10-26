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
        return create(M.Party(issuer=self.issuer, owner=self.owner, lot=lot))

    @choice(controller=owner, consuming=False)
    def Size(self, cid: ContractId[M.Note]) -> Decimal:
        for _k in range(0, 2):
            note = fetch(cid)
        return note.lot.amount
