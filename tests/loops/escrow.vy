from datetime import datetime

from forge.models import ContractId, Decimal, Party, choice, template


struct EscrowTerms:
    amount: Decimal
    deadline: datetime


@template
class Payout:
    payer: Party
    receiver: Party
    amount: Decimal

    signatory: list[Party] = [payer]
    observer: list[Party] = [receiver]


# The arbiter holds the buyer's money until the deal ends.
@template
class Escrow:
    buyer: Party
    seller: Party
    arbiter: Party
    terms: EscrowTerms

    signatory: list[Party] = [buyer]
    observer: list[Party] = [seller, arbiter]
    ensure: bool = terms.amount > Decimal(0)

    @choice(controller=arbiter, consuming=True)
    def Release(self) -> ContractId[Payout]:
        return create(Payout(payer=self.arbiter, receiver=self.seller, amount=self.terms.amount))

    @choice(controller=arbiter, consuming=True)
    def Refund(self) -> ContractId[Payout]:
        now = datetime.now()
        assert now > self.terms.deadline, "refund is allowed only after the deadline"
        return create(Payout(payer=self.arbiter, receiver=self.buyer, amount=self.terms.amount))
