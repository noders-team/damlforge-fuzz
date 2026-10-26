from enum import Enum, auto

from forge.models import Party, template


class Kind(Enum):
    CASH = auto()


@template
class CASH:
    owner: Party

    signatory: list[Party] = [owner]
