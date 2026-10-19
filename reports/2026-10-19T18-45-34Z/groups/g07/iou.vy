from forge.models import ContractId, Decimal, Party, choice, template


@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal
    currency: str

    signatory: list[Party] = [issuer]
    observer: list[Party] = [owner]
    ensure: bool = amount > Decimal(0)

    @choice(controller=owner, consuming=True)
    def Transfer(self, new_owner: Party) -> ContractId[Iou]:
        return create(
            Iou(issuer=self.issuer, owner=new_owner, amount=self.amount, currency=self.currency)
        )

    @choice(controller=owner, consuming=True)
    def Split(self, split_amount: Decimal) -> tuple[ContractId[Iou], ContractId[Iou]]:
        assert split_amount > Decimal(0), "split amount must be positive"
        assert split_amount < self.amount, "split amount must be less than the full amount"
        first = create(
            Iou(issuer=self.issuer, owner=self.owner, amount=split_amount, currency=self.currency)
        )
        rest = create(
            Iou(
                issuer=self.issuer,
                owner=self.owner,
                amount=self.amount >> split_amount,
                currency=self.currency,
            )
        )
        return (first, rest)
