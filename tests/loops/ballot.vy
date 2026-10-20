from forge.models import ContractId, GenMap, Party, choice, template
import DA.Map as M


def count_yes(votes: GenMap[Party, bool]) -> int:
    answers: list[bool] = M.values(votes)
    count = 0
    for in_favor in answers:
        if in_favor:
            count = count + 1
    return count


@template
class Ballot:
    organizer: Party
    voters: list[Party]
    votes: GenMap[Party, bool]

    signatory: list[Party] = [organizer]
    observer: list[Party] = voters

    @choice(controller=voter, consuming=True)
    def CastVote(self, voter: Party, in_favor: bool) -> ContractId[Ballot]:
        assert voter in self.voters, "voter is not on the voter list"
        assert M.lookup(voter, self.votes) is None, "voter has already voted"
        new_votes: GenMap[Party, bool] = M.insert(voter, in_favor, self.votes)
        return create(Ballot(organizer=self.organizer, voters=self.voters, votes=new_votes))

    @choice(controller=organizer, consuming=True)
    def Close(self) -> bool:
        return count_yes(self.votes) * 2 > len(self.voters)
