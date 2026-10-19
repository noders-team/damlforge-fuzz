from forge.models import GenMap, Party


def has_voted(votes: GenMap[Party, bool], voter: Party) -> bool:
    return voter in votes
