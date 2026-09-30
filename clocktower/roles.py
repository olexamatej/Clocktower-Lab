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

# Ability summaries; official character rules: https://wiki.bloodontheclocktower.com/Bad_Moon_Rising
_BMR = [
    (
        "grandmother",
        "Grandmother",
        "townsfolk",
        "Start knowing a good player and their character. If the Demon kills them, you die too.",
    ),
    (
        "sailor",
        "Sailor",
        "townsfolk",
        "Each night choose a living player: you or they are drunk until dusk. While sober, you cannot die.",
    ),
    (
        "chambermaid",
        "Chambermaid",
        "townsfolk",
        "Each night choose two other living players: learn how many woke tonight to use their own ability.",
    ),
    (
        "exorcist",
        "Exorcist",
        "townsfolk",
        "Each night after the first choose a different player from last night. If they are the Demon, they learn who you are and do not wake tonight.",
    ),
    (
        "innkeeper",
        "Innkeeper",
        "townsfolk",
        "Each night after the first choose two players. They cannot die tonight, but one is drunk until dusk.",
    ),
    (
        "gambler",
        "Gambler",
        "townsfolk",
        "Each night after the first choose a player and guess their character. If wrong, you die.",
    ),
    (
        "gossip",
        "Gossip",
        "townsfolk",
        "Each day you may publicly gossip a definite statement. If true, a player dies tonight.",
    ),
    (
        "courtier",
        "Courtier",
        "townsfolk",
        "Once per game at night choose a character. They are drunk for three nights and three days.",
    ),
    (
        "professor",
        "Professor",
        "townsfolk",
        "Once per game at night after the first choose a dead player. If Townsfolk, they return to life with their ability refreshed.",
    ),
    (
        "minstrel",
        "Minstrel",
        "townsfolk",
        "When a Minion dies by execution, everyone except you is drunk until dusk tomorrow.",
    ),
    (
        "tea_lady",
        "Tea Lady",
        "townsfolk",
        "If your two nearest living neighbors are both good, neither can die.",
    ),
    ("pacifist", "Pacifist", "townsfolk", "A good player executed while you are alive might survive."),
    ("fool", "Fool", "townsfolk", "The first time you would die, you survive instead."),
    (
        "goon",
        "Goon",
        "outsider",
        "Each night the first player to choose you with their ability becomes drunk until dusk. You become their alignment.",
    ),
    (
        "lunatic",
        "Lunatic",
        "outsider",
        "You believe you are an evil Demon. Your choices have no Demon effect; the real Demon learns who you are and your night choices.",
    ),
    ("tinker", "Tinker", "outsider", "The Storyteller may cause you to die at any time."),
    (
        "moonchild",
        "Moonchild",
        "outsider",
        "When you learn you died, publicly choose a living player. If they were good when chosen, they die tonight.",
    ),
    (
        "godfather",
        "Godfather",
        "minion",
        "Start knowing the Outsider characters in play. If an Outsider died today, choose a player tonight to die. Setup adds or removes one Outsider.",
    ),
    (
        "devils_advocate",
        "Devil's Advocate",
        "minion",
        "Each night choose a living player different from last night. They survive execution tomorrow.",
    ),
    (
        "assassin",
        "Assassin",
        "minion",
        "Once per game at night after the first choose a player to die, overcoming protection, including the Goon.",
    ),
    (
        "mastermind",
        "Mastermind",
        "minion",
        "If the Demon's execution death would end the game, play one extra day. The next executed player's team loses; no execution means good wins.",
    ),
    (
        "zombuul",
        "Zombuul",
        "demon",
        "Each night after the first, if nobody died today, choose a player to die. Your first death instead leaves you alive but registering as dead.",
    ),
    (
        "pukka",
        "Pukka",
        "demon",
        "Each night choose a player to poison. Your previous poisoned target dies, then becomes healthy.",
    ),
    (
        "shabaloth",
        "Shabaloth",
        "demon",
        "Each night after the first choose two players to die in order. A dead player chosen last night may return to life.",
    ),
    (
        "po",
        "Po",
        "demon",
        "Each night after the first choose one player to die, or nobody. After choosing nobody, your next action must choose three players to die in order.",
    ),
]
ROLES.update({row[0]: Role(*row) for row in _BMR})
BAD_MOON_RISING = Script(
    "bad_moon_rising",
    tuple(row[0] for row in _BMR),
    ("sailor", "courtier", "godfather", "devils_advocate", "lunatic", "pukka", "grandmother", "chambermaid"),
    (
        "sailor",
        "innkeeper",
        "courtier",
        "gambler",
        "devils_advocate",
        "exorcist",
        "lunatic",
        "zombuul",
        "pukka",
        "shabaloth",
        "po",
        "assassin",
        "godfather",
        "professor",
        "gossip",
        "moonchild",
        "tinker",
        "chambermaid",
    ),
)
SCRIPTS[BAD_MOON_RISING.id] = BAD_MOON_RISING
SCRIPT_NAMES = {"trouble_brewing": "Trouble Brewing", "bad_moon_rising": "Bad Moon Rising"}

# The full script is available for bluffing and reference. The current engine
# supports the explicit ten-player roster below; other setups are rejected.
_SV = [
    ("clockmaker", "Clockmaker", "townsfolk", "Start knowing the shortest seating distance between the Demon and a Minion."),
    ("dreamer", "Dreamer", "townsfolk", "Each night choose another player. Learn one good and one evil character; one is their character."),
    ("snake_charmer", "Snake Charmer", "townsfolk", "Each night choose a living player. If a Demon, swap characters and alignments with them; the former Demon becomes poisoned."),
    ("mathematician", "Mathematician", "townsfolk", "Each night learn how many players' abilities worked abnormally since dawn because of another character's ability."),
    ("flowergirl", "Flowergirl", "townsfolk", "Each night after the first learn whether a Demon voted during the previous day."),
    ("town_crier", "Town Crier", "townsfolk", "Each night after the first learn whether any Minion nominated during the previous day."),
    ("oracle", "Oracle", "townsfolk", "Each night after the first learn how many dead players are evil."),
    ("savant", "Savant", "townsfolk", "Each day privately receive two statements from the Storyteller: one true and one false."),
    ("seamstress", "Seamstress", "townsfolk", "Once per game at night choose two other players and learn whether their alignments match."),
    ("philosopher", "Philosopher", "townsfolk", "Once per game at night choose a good character and gain its ability. An in-play player with that character becomes drunk."),
    ("artist", "Artist", "townsfolk", "Once per game during the day privately ask the Storyteller a yes/no question and receive a truthful answer."),
    ("juggler", "Juggler", "townsfolk", "On your first day publicly guess up to five players' characters. That night learn how many guesses were correct."),
    ("sage", "Sage", "townsfolk", "If the Demon kills you, learn two players, one of whom is the Demon that killed you."),
    ("mutant", "Mutant", "outsider", "If you are mad about being an Outsider, the Storyteller may execute you."),
    ("sweetheart", "Sweetheart", "outsider", "When you die, a player becomes drunk for the rest of the game."),
    ("barber", "Barber", "outsider", "If you die during the day or night, the Demon may swap the characters of two players who are not Demons that night."),
    ("klutz", "Klutz", "outsider", "When you learn you died, publicly choose a living player. If they are evil, your team loses."),
    ("evil_twin", "Evil Twin", "minion", "You and an opposing player know each other and each other's characters. Executing the good twin makes evil win. Good cannot win while both twins live."),
    ("witch", "Witch", "minion", "Each night choose a player. If they nominate tomorrow, they die; their nomination still counts. Your ability stops when only three players live."),
    ("cerenovus", "Cerenovus", "minion", "Each night choose a player and a good character. Tomorrow they must be mad about being that character or risk execution."),
    ("pit_hag", "Pit-Hag", "minion", "Each night after the first choose a player and a character not in play for them to become. If a Demon is created, tonight's deaths are arbitrary."),
    ("fang_gu", "Fang Gu", "demon", "Each night after the first choose a player to die. The first Outsider you would kill instead becomes an evil Fang Gu and you die. Setup adds one Outsider."),
    ("vigormortis", "Vigormortis", "demon", "Each night after the first choose a player to die. Minions you kill retain their abilities and poison one of their Townsfolk neighbors. Setup removes one Outsider."),
    ("no_dashii", "No Dashii", "demon", "Each night after the first choose a player to die. Your two Townsfolk neighbors are poisoned."),
    ("vortox", "Vortox", "demon", "Each night after the first choose a player to die. Townsfolk abilities give false information. If nobody is executed during a day, evil wins."),
]
ROLES.update({row[0]: Role(*row) for row in _SV})
SV_RUN_ROLES = (
    "clockmaker", "dreamer", "flowergirl", "town_crier", "oracle", "seamstress", "sage",
    "evil_twin", "witch", "vortox",
)
SECTS_AND_VIOLETS = Script(
    "sects_and_violets",
    tuple(row[0] for row in _SV),
    ("evil_twin", "witch", "clockmaker", "dreamer", "seamstress"),
    ("witch", "vortox", "dreamer", "flowergirl", "town_crier", "oracle", "seamstress"),
)
SCRIPTS[SECTS_AND_VIOLETS.id] = SECTS_AND_VIOLETS
SCRIPT_NAMES[SECTS_AND_VIOLETS.id] = "Sects & Violets"
