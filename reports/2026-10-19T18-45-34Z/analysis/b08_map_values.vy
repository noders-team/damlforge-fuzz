from forge.models import GenMap, Party


def yes_votes(votes: GenMap[Party, bool]) -> int:
    count = 0
    for v in votes.values():
        if v:
            count = count + 1
    return count
