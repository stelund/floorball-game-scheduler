import collections
import re
import sys
import fire
import icalendar
import datetime
import random
import pytz
import yaml
from dataclasses import dataclass, field


@dataclass
class Player:
    name: str
    pool: str
    games: list["Game"] = field(default_factory=list)

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
        return self.name == other.name

    def __str__(self):
        return str(self.name)

    def __repr__(self):
        return str(self)

    def __hash__(self) -> int:
        return hash("Player" + str(self.name))

    def __lt__(self, other):
        return self.name < other.name

    @property
    def is_trainer_kid(self):
        return self.name.endswith("*")

    @property
    def small_games_count(self):
        return sum((1 for g in self.games if g.player_count == 11))
            
    @property
    def large_games_count(self):
        return sum((1 for g in self.games if g.player_count == 16))

    @property
    def cell_ref(self):
        return f"=A{self.number}"
            


@dataclass
class Game:
    start_date: datetime.datetime
    end_date: datetime.datetime
    location: str
    players: set[Player] = field(default_factory=set)
    year: int = 0

    @property
    def is_home(self):
        return re.match("Sk.ndalshallen", self.location)

    @property
    def player_count(self) -> int:
        return {
            2012: 16,
            2013: 11,
        }[self.year]

    @property
    def pool_counts(self):
        pool_counts = {
            2012: {"p12-rutin": 6, "p12-junior": 3, "p13-stark": 3, "p13-mellan": 4},
            2013: {"p13-stark": 2, "p13-mellan": 7, "p13-junior": 2},
        }[self.year]
        for pool_name, count in pool_counts.items():
            yield pool_name, count

    def is_same_weekend(self, other):
        return self.start_date.isocalendar()[1] == other.start_date.isocalendar()[1]

    def setup(self, pools):
        print("setup match", self.year)
        for pool_name, count in self.pool_counts:
            print(pool_name)
            players = set(pools[pool_name])
            new = set()

            def add_players(nominated):
                nominated = list(nominated)
                while len(new) != count and len(self.players) != self.player_count and nominated:
                    p = random.choice(nominated)
                    nominated.remove(p)
                    self.players.add(p)
                    new.add(p)
                    players.remove(p)
                    p.games.append(self)
                print("added players", new, count, players)

            while len(new) != count and players and len(self.players) != self.player_count:
                print("WHILE", len(new), count, players)
                candidates = get_least_played_players(players - set(self.players))
                if len(self.players) < 2 and only_trainer_kids(candidates):
                    candidates = only_trainer_kids(candidates)

                print(pool_name, candidates, new, count)

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
                    print("PRIO", priority_candidates)
                    continue

                add_players(candidates)

            print(pool_name, count, new)

    def setup_old(self, players):
        def add_players(nominated):
            nominated = list(nominated)
            while len(self.players) != self.player_count and nominated:
                p = random.choice(nominated)
                nominated.remove(p)
                self.players.append(p)
                p.games.append(self)

        while len(self.players) != self.player_count:
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


def get_players_with_least_games(players: set[Player], property="games_count"):
    nominated = set()
    least_games = 1000
    for p in players:
        if getattr(p, property) < least_games:
            nominated = {p}
            least_games = getattr(p, property)
        if getattr(p, property) == least_games:
            nominated.add(p)
    return nominated


def get_least_played_players(players: set[Player]):
    return get_players_with_least_games(players, "games_count")


def get_players_with_least_home_games(players: set[Player]):
    return get_players_with_least_games(players, "home_games_count")


def get_players_with_least_away_games(players: set[Player]):
    return get_players_with_least_games(players, "away_games_count")


def players_not_playing_same_weekend(players: set[Player], game: Game):
    nominated = set()
    for p in players:
        for g in reversed(p.games):
            if not game.is_same_weekend(g):
                nominated.add(p)
                continue
    return nominated


def only_trainer_kids(players: set[Player]) -> set[Player]:
    return {p for p in players if p.is_trainer_kid}


def load_calendar(calendar="calendar.ical"):
    games = []
    tz_sweden = pytz.timezone("Europe/Stockholm")
    now = pytz.utc.localize(datetime.datetime.now())
    with open(calendar, "r") as fp:
        gcal = icalendar.Calendar.from_ical(fp.read())
        for component in gcal.walk():
            if component.name == "VEVENT" and "Match" in component.get("summary"):
                if component.get("dtstart").dt < now or component.get(
                    "dtstart"
                ).dt > datetime.datetime(2025, 1, 1, tzinfo=tz_sweden):
                    continue

                year = int(re.findall(r"20\d\d", component.get("summary"))[0])
                # print(year, component.get("summary"))
                games.append(
                    Game(
                        component.get("dtstart").dt,
                        component.get("dtend").dt,
                        str(component.get("location")),
                        year=year,
                    )
                )
    return games


def describe_game(game: Game):
    print(
        f"{game.start_date.strftime('%Y-%m-%d %H:%M')}: {game.location} players: {len(game.players)}"
    )
    only_trainer_kids_count = sum([1 for p in game.players if p.is_trainer_kid])
    pools = collections.defaultdict(set)
    for p in game.players:
        pools[p.pool].add(p)

    print(f"trainer kids: {only_trainer_kids_count}", end=" ")
    for pool, players in sorted(pools.items(), key=lambda x: x[0]):
        print(f"{pool}: {len(players)}", end=" ")
    print()


def main(spelare=23):
    with open("players.yaml", "r") as fp:
        pools: dict[str:Player] = {
            pool: {Player(p, pool) for p in players}
            for pool, players in yaml.safe_load(fp).items()
        }

    pools["trainer_kids"] = {
        player for pool in pools.values() for player in pool if player.is_trainer_kid
    }
    print("POOLS", pools)

    # players = set(Player(i) for i in range(1, spelare + 1))
    players = set()
    for p in pools.values():
        players.update(p)
    print("PLAYERS", players)
    print()
    games = load_calendar()
    for game in games:
        game.setup(pools)

    for p in sorted(list(players)):
        print(
            f"{str(p):<30} matcher: {p.games_count} hemma matcher: {p.home_games_count} "
            f"borta matcher: {p.away_games_count} matcher samma helg: {p.same_weekend_games_count} "
            f"femmanna: {p.large_games_count} fyrmanna: {p.small_games_count}"
        )

    for g in games:
        describe_game(g)


if __name__ == "__main__":
    fire.Fire(main)
