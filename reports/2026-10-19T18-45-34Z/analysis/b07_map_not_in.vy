from forge.models import GenMap, Party


def is_new(votes: GenMap[Party, bool], voter: Party) -> bool:
    return voter not in votes
