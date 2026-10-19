from forge.models import GenMap, Party


def mark(votes: GenMap[Party, bool], voter: Party) -> GenMap[Party, bool]:
    votes[voter] = True
    return votes
