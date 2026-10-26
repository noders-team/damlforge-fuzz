from forge.models import ContractId, Decimal, Party, choice, template


struct Lot:
    amount: Decimal


@template
class Note:
    owner: Party
    lot: Lot

    signatory: list[Party] = [owner]

    @choice(controller=owner, consuming=False)
    def Size(self, cid: ContractId[Note]) -> Decimal:
        for _k in range(0, 2):
            note = fetch(cid)
        return note.lot.amount
