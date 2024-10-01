import collections
import re
import sys
import fire
import icalendar
import datetime
import random
import pytz
import yaml
import unicodedata
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
        return sum((1 for g in self.games if g.player_count == 9))

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
            2013: 9,
        }[self.year]

    @property
    def pool_counts(self):
        pool_counts = {
            2012: {"p12-rutin": 6, "p12-junior": 3, "p13-stark": 3, "p13-mellan": 5},
            2013: {"p13-stark": 2, "p13-mellan": 5, "p13-junior": 2},
        }[self.year]
        for pool_name, count in pool_counts.items():
            yield pool_name, count

    def is_same_weekend(self, other):
        return self.start_date.isocalendar()[1] == other.start_date.isocalendar()[1]

    def setup(self, pools, unavailabilities):
        for pool_name, count in self.pool_counts:
            players = set(pools[pool_name])
            game_key = self.start_date.strftime("%Y-%m-%d %H:%M")
            for p in list(players):
                if game_key in unavailabilities.get(p.name, []):
                    players.remove(p)
                    continue

            new = set()

            def add_players(nominated):
                nominated = list(nominated)
                groups = collections.defaultdict(list)
                if self.player_count == 9:
                    for p in nominated:
                        groups[p.small_games_count].append(p)
                else:
                    for p in nominated:
                        groups[p.large_games_count].append(p)
                
                keys = sorted(list(groups.keys()))
                for key in keys:
                    group = groups[key] 
                    while (
                        len(new) != count
                        and len(self.players) != self.player_count
                        and group
                    ):
                        p = random.choice(group)
                        group.remove(p)
                        self.players.add(p)
                        new.add(p)
                        players.remove(p)
                        p.games.append(self)
                    #print("added players", key, new, count, players)

            while (
                len(new) != count and players and len(self.players) != self.player_count
            ):
                candidates = get_least_played_players(players - set(self.players))
                if len(self.players) < 2 and only_trainer_kids(candidates):
                    candidates = only_trainer_kids(candidates)

                # print(pool_name, candidates, new, count)

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

            # print(pool_name, count, new)


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


def load_previous_games(games: list[Game]):
    with open("previous_games.yaml", "r") as fp:
        previous_games = yaml.safe_load(fp)

    for game in games:
        key = f"{game.start_date.strftime('%Y-%m-%d %H:%M')} {game.location}"
        previous_players = previous_games.pop(key, [])
        for player_name in previous_players:
            game.players.add(Player(player_name, "unknown"))

    if previous_games:
        print(f"Didnt fint previous game {''.join([k for k in previous_games])}")
        sys.exit(1)


def load_calendar(calendar="calendar.ical"):
    games = []
    tz_sweden = pytz.timezone("Europe/Stockholm")
    start_of_season = datetime.datetime(2024, 9, 25, tzinfo=tz_sweden)
    end_of_season = datetime.datetime(2025, 1, 1, tzinfo=tz_sweden)

    with open(calendar, "r") as fp:
        gcal = icalendar.Calendar.from_ical(fp.read())
        for component in gcal.walk():
            if component.name == "VEVENT" and "Match" in component.get("summary"):
                if (
                    component.get("dtstart").dt < start_of_season
                    or component.get("dtstart").dt > end_of_season
                ):
                    continue

                year = int(re.findall(r"20\d\d", component.get("summary"))[0])
                # print(year, component.get("summary"))
                games.append(
                    Game(
                        component.get("dtstart").dt,
                        component.get("dtend").dt,
                        str(component.get("location")).strip(),
                        year=year,
                    )
                )
    return games


def describe_game(game: Game):
    print(
        f"{game.start_date.strftime('%Y-%m-%d %H:%M')}: {game.location} spelare: {len(game.players)}"
    )
    only_trainer_kids_count = sum([1 for p in game.players if p.is_trainer_kid])
    pools = collections.defaultdict(set)
    for p in game.players:
        pools[p.pool].add(p)

    print(f"tränarbarn: {only_trainer_kids_count}", end=" ")
    for pool, players in sorted(pools.items(), key=lambda x: x[0]):
        print(f"{pool}: {len(players)}", end=" ")
    print()
    for p in game.players:
        print(p.name)


def main(csv=False):
    with open("players.yaml", "r") as fp:
        players_data = yaml.safe_load(fp)
    pools: dict[str:Player] = {
        pool: {Player(p, pool) for p in players}
        for pool, players in players_data["pools"].items()
    }
    unavailabilities = players_data["unavailabilities"]

    pools["trainer_kids"] = {
        player for pool in pools.values() for player in pool if player.is_trainer_kid
    }
    # print("POOLS", pools)

    players = set()
    for p in pools.values():
        players.update(p)
    games = load_calendar()
    load_previous_games(games)    
    for game in games:
        print(f"================= setup {game}")
        game.setup(pools, unavailabilities)

    if csv:
        print(
            "Spelare,Matcher,Hemma matcher,Borta matcher,Matcher samma helg,5-manna,4-manna"
        )
    for p in sorted(list(players)):
        if csv:
            print(
                f"{str(p)},{p.games_count},{p.home_games_count},"
                f"{p.away_games_count},{p.same_weekend_games_count},"
                f"{p.large_games_count},{p.small_games_count}"
            )
        else:
            print(
                f"{str(p):<30} matcher: {p.games_count} hemma matcher: {p.home_games_count} "
                f"borta matcher: {p.away_games_count} matcher samma helg: {p.same_weekend_games_count} "
                f"5-manna: {p.large_games_count} 4-manna: {p.small_games_count}"
            )

    for g in games:
        describe_game(g)


if __name__ == "__main__":
    fire.Fire(main)
