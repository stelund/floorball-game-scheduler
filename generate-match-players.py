import fire
import icalendar
import datetime
import random
import pytz
from typing import List, Set
from dataclasses import dataclass, field


@dataclass
class Player:
    number: int
    games: List["Game"] = field(default_factory=list)

    @property
    def games_count(self):
        return len(self.games)

    @property
    def home_games_count(self):
        return len([1 for x in self.games if x.is_home])

    @property
    def away_games_count(self):
        return len([1 for x in self.games if not x.is_home])

    @property
    def same_weekend_games_count(self):
        count = 0
        games = list(self.games)
        for i, g in enumerate(games):
            for g2 in games[i + 1 :]:
                if g2.is_same_weekend(g):
                    count += 1
        return count

    def __eq__(self, other):
        return self.number == other.number

    def __str__(self):
        return str(self.number)

    def __repr__(self):
        return str(self)

    def __hash__(self) -> int:
        return hash("Player" + str(self.number))

    def __lt__(self, other):
        return self.number < other.number

    @property
    def is_trainer_kid(self):
        return self.number in [2, 16, 19, 20, 22]

    @property
    def cell_ref(self):
        return f"=A{self.number}"


@dataclass
class Game:
    start_date: datetime.datetime
    end_date: datetime.datetime
    location: str
    players: List[Player] = field(default_factory=list)

    @property
    def is_home(self):
        return self.location == "Sköndalshallen"

    def is_same_weekend(self, other):
        return self.start_date.isocalendar()[1] == other.start_date.isocalendar()[1]

    def setup(self, count, players):
        def add_players(nominated):
            nominated = list(nominated)
            while len(self.players) != count and nominated:
                p = random.choice(nominated)
                nominated.remove(p)
                self.players.append(p)
                p.games.append(self)


        while len(self.players) != count:
            candidates = get_least_played_players(players - set(self.players))
            if len(self.players) < 2 and only_trainer_kids(candidates):
                candidates = only_trainer_kids(candidates)

            priority_candidates = (
                get_players_with_least_home_games(candidates)
                if self.is_home
                else get_players_with_least_away_games(candidates)
            )

            short_list = players_not_playing_same_weekend(priority_candidates, self)
            if short_list:
                add_players(short_list)
                continue

            short_list = players_not_playing_same_weekend(candidates, self)
            if short_list:
                add_players(short_list)
                continue

            if priority_candidates:
                add_players(priority_candidates)
                continue

            add_players(candidates)

    def __str__(self):
        return f"Game(start_date={self.start_date.isoformat()} location={self.location}, players={self.players})"

    def __repr__(self):
        return str(self)

    def __hash__(self) -> int:
        return hash("Game" + str(self.start_date) + self.location)


def get_players_with_least_games(players: Set[Player], property="games_count"):
    nominated = set()
    least_games = 1000
    for p in players:
        if getattr(p, property) < least_games:
            nominated = {p}
            least_games = getattr(p, property)
        if getattr(p, property) == least_games:
            nominated.add(p)
    return nominated


def get_least_played_players(players: Set[Player]):
    return get_players_with_least_games(players, "games_count")


def get_players_with_least_home_games(players: Set[Player]):
    return get_players_with_least_games(players, "home_games_count")


def get_players_with_least_away_games(players: Set[Player]):
    return get_players_with_least_games(players, "away_games_count")


def players_not_playing_same_weekend(players: Set[Player], game: Game):
    nominated = set()
    for p in players:
        for g in reversed(p.games):
            if not game.is_same_weekend(g):
                nominated.add(p)
                continue
    return nominated


def only_trainer_kids(players: Set[Player]) -> Set[Player]:
    return {p for p in players if p.is_trainer_kid}


def load_calendar(calendar="calendar.ical"):
    games = []
    now = pytz.utc.localize(datetime.datetime.utcnow())
    with open(calendar, "r") as fp:
        gcal = icalendar.Calendar.from_ical(fp.read())
        for component in gcal.walk():
            if component.name == "VEVENT" and "Match" in component.get("summary"):
                if component.get("dtstart").dt < now:
                    continue

                games.append(
                    Game(
                        component.get("dtstart").dt,
                        component.get("dtend").dt,
                        str(component.get("location")),
                    )
                )
    return games

player_names = [
    
]


def main(spelare=23, per_match=12):
    players = set(Player(p) for i in range(1, spelare + 1))
    games = load_calendar()
    for game in games:
        game.setup(per_match, players)

    for p in sorted(list(players)):
        print(
            f"{p}, matcher: {p.games_count} hemma matcher: {p.home_games_count} borta matcher: {p.away_games_count} matcher samma helg: {p.same_weekend_games_count} {p.is_trainer_kid and 'lagledarebarn' or ''}"
        )

    print(
        "\t".join(
            [
                (f"{g.location}: {g.start_date.strftime('%Y-%m-%d %H:%M')} ")
                for g in games
            ]
        )
    )
    for row in range(per_match):
        print("\t".join([g.players[row].cell_ref for g in games]))


if __name__ == "__main__":
    fire.Fire(main)
