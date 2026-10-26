from forge.models import Decimal, Party, choice, template
from models import double, fee


def net(amount: Decimal) -> Decimal:
    return double(amount) - fee(amount, Decimal(0.1))


@template
class Pot:
    owner: Party
    amount: Decimal

    signatory: list[Party] = [owner]

    @choice(controller=owner, consuming=False)
    def Paid(self, rate: Decimal) -> Decimal:
        return self.amount - fee(self.amount, rate)

    @choice(controller=owner, consuming=False)
    def Net(self) -> Decimal:
        return net(double(self.amount))
