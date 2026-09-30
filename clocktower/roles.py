"""Script data, kept separate from rules resolution and transport."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Role:
    id: str
    name: str
    team: str
    ability: str


_DATA = [
    (
        "washerwoman",
        "Washerwoman",
        "townsfolk",
        "On your first night, learn that one of two players is a specific Townsfolk.",
    ),
    (
        "librarian",
        "Librarian",
        "townsfolk",
        "On your first night, learn that one of two players is a specific Outsider, or that no Outsiders are in play.",
    ),
    (
        "investigator",
        "Investigator",
        "townsfolk",
        "On your first night, learn that one of two players is a specific Minion.",
    ),
    (
        "chef",
        "Chef",
        "townsfolk",
        "On your first night, learn how many adjacent pairs of evil players there are.",
    ),
    (
        "empath",
        "Empath",
        "townsfolk",
        "Each night learn how many of your two nearest living neighbours are evil.",
    ),
    (
        "fortune_teller",
        "Fortune Teller",
        "townsfolk",
        "Each night choose two different players; learn whether either is a Demon. One good player registers as a Demon to you.",
    ),
    (
        "undertaker",
        "Undertaker",
        "townsfolk",
        "Each night after the first, learn the character of the player who died by execution today.",
    ),
    (
        "monk",
        "Monk",
        "townsfolk",
        "Each night after the first, choose another player to protect from the Demon tonight.",
    ),
    (
        "ravenkeeper",
        "Ravenkeeper",
        "townsfolk",
        "If you die at night, choose a player and learn their character.",
    ),
    (
        "virgin",
        "Virgin",
        "townsfolk",
        "The first time you are nominated, if the nominator is a Townsfolk, they are executed immediately.",
    ),
    (
        "slayer",
        "Slayer",
        "townsfolk",
        "Once per game during the day publicly choose a player: if they are a Demon, they die.",
    ),
    ("soldier", "Soldier", "townsfolk", "You are safe from the Demon."),
    (
        "mayor",
        "Mayor",
        "townsfolk",
        "If exactly three players live and nobody is executed, good wins. If you die at night another player may die instead.",
    ),
    (
        "butler",
        "Butler",
        "outsider",
        "Each night choose another player as master. You may vote only when your master also votes.",
    ),
    ("drunk", "Drunk", "outsider", "You think you are a Townsfolk but have no Townsfolk ability."),
    ("recluse", "Recluse", "outsider", "You may register as evil and as a Minion or Demon, even while dead."),
    ("saint", "Saint", "outsider", "If you die by execution, evil wins."),
    (
        "poisoner",
        "Poisoner",
        "minion",
        "Each night choose a player: they are poisoned tonight and tomorrow day.",
    ),
    (
        "spy",
        "Spy",
        "minion",
        "Each night see the Grimoire. You may register as good and as a Townsfolk or Outsider, even while dead.",
    ),
    (
        "scarlet_woman",
        "Scarlet Woman",
        "minion",
        "If at least five players are alive when the Demon dies, you become the Demon.",
    ),
    ("baron", "Baron", "minion", "Setup adds two Outsiders and removes two Townsfolk."),
    (
        "imp",
        "Imp",
        "demon",
        "Each night after the first choose a player to kill. If you kill yourself this way, a living Minion becomes the Imp.",
    ),
]
ROLES = {r[0]: Role(*r) for r in _DATA}
TOWNSFOLK = [r.id for r in ROLES.values() if r.team == "townsfolk"]
OUTSIDERS = [r.id for r in ROLES.values() if r.team == "outsider"]
MINIONS = [r.id for r in ROLES.values() if r.team == "minion"]
# Number of Townsfolk, Outsiders, Minions, Demons before setup modifiers.
COUNTS = {
    5: (3, 0, 1, 1),
    6: (3, 1, 1, 1),
    7: (5, 0, 1, 1),
    8: (5, 1, 1, 1),
    9: (5, 2, 1, 1),
    10: (7, 0, 2, 1),
    11: (7, 1, 2, 1),
    12: (7, 2, 2, 1),
    13: (9, 0, 3, 1),
    14: (9, 1, 3, 1),
    15: (9, 2, 3, 1),
}


@dataclass(frozen=True)
class Script:
    id: str
    roles: tuple[str, ...]
    first_night: tuple[str, ...]
    other_nights: tuple[str, ...]


TROUBLE_BREWING = Script(
    "trouble_brewing",
    tuple(ROLES),
    (
        "poisoner",
        "spy",
        "washerwoman",
        "librarian",
        "investigator",
        "chef",
        "empath",
        "fortune_teller",
        "butler",
    ),
    ("poisoner", "monk", "imp", "ravenkeeper", "undertaker", "empath", "fortune_teller", "butler", "spy"),
)
SCRIPTS = {TROUBLE_BREWING.id: TROUBLE_BREWING}
