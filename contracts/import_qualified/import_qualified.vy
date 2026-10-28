from forge.models import ContractId, Decimal, Party, choice, template
from forge.builtins.daml_lang import create, fetch
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
        return create(M.Note(issuer=self.issuer, owner=self.owner, lot=lot))

    @choice(controller=owner, consuming=False)
    def Size(self, cid: ContractId[M.Note]) -> Decimal:
        note = fetch(cid)
        return note.lot.amount
