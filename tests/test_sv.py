"""Supported Sects & Violets roster: false information, twin and curse boundaries."""

import random

import pytest

from clocktower.config import GameConfig, PlayerConfig
from clocktower.roles import ROLES, SV_RUN_ROLES
from clocktower.sv import SectsAndVioletsEngine


def game(seed=42):
    config = GameConfig(
        script="sects_and_violets",
        players=[PlayerConfig(id=f"p{i}", name=f"P{i}") for i in range(10)],
        roles=list(SV_RUN_ROLES),
        shuffle_roles=False,
        seed=seed,
    )
    e = SectsAndVioletsEngine(config)
    e.day = 2
    e.phase = "night"
    return e


def drive(gen, choose=lambda d: d.options[0]):
    try:
        d = next(gen)
        while True:
            assert d.options
            a = choose(d)
            d.validate(a, 1500)
            d = gen.send(a)
    except StopIteration:
        return


def info(e):
    return next(v["data"]["value"] for v in reversed(e.events) if v["kind"] == "information")


@pytest.mark.parametrize("vortox", [True, False])
def test_clockmaker_and_oracle_numbers(vortox):
    e = game()
    e.players[9].alive = vortox
    drive(e._night_role(e.players[0]))
    assert (info(e) == 1) is (not vortox)
    drive(e._night_role(e.players[4]))
    actual = 0 if vortox else 1
    assert (info(e) == actual) is (not vortox)


@pytest.mark.parametrize(
    "role,index,key,event",
    [
        ("flowergirl", 2, "demon_voted", ("vote", {"votes": {"p9": True}})),
        ("town_crier", 3, "minion_nominated", ("nomination", {"nominator": "p8", "nominee": "p0"})),
    ],
)
@pytest.mark.parametrize("vortox", [True, False])
def test_previous_day_boolean_information(role, index, key, event, vortox):
    e = game()
    e.players[9].alive = vortox
    e.day = 1
    e.emit(*event)
    e.day = 2
    drive(e._night_role(e.players[index]))
    assert info(e)[key] is (not vortox)
    e.day = 3
    drive(e._night_role(e.players[index]))
    assert info(e)[key] is vortox


@pytest.mark.parametrize("poisoned", [False, True])
def test_vortox_dreamer_both_wrong_and_sage_no_demon_even_if_poisoned(monkeypatch, poisoned):
    e = game()
    monkeypatch.setattr(e, "impaired", lambda p: poisoned and p.id in ("p1", "p6"))
    drive(e._night_role(e.players[1]), lambda d: {"type": "choose", "target": "p0"})
    pair = info(e)["characters"]
    assert len(pair) == 2 and "clockmaker" not in pair
    assert ROLES[pair[0]].team in ("townsfolk", "outsider") and ROLES[pair[1]].team in ("minion", "demon")
    e._kill(e.players[6], "demon", e.players[9])
    assert "p9" not in info(e)["demon_in"]


def test_healthy_dreamer_and_sage_when_vortox_impaired(monkeypatch):
    e = game()
    monkeypatch.setattr(e, "impaired", lambda p: p.id == "p9")
    drive(e._night_role(e.players[1]), lambda d: {"type": "choose", "target": "p8"})
    assert "witch" in info(e)["characters"]
    e._kill(e.players[6], "demon", e.players[9])
    assert "p9" in info(e)["demon_in"]


@pytest.mark.parametrize("vortox", [True, False])
def test_seamstress_once_per_game_with_false_alignment(vortox):
    e = game()
    e.players[9].alive = vortox
    drive(e._night_role(e.players[5]), lambda d: {"type": "choose", "targets": ["p0", "p1"]})
    assert info(e)["same_alignment"] is (not vortox)
    assert "seamstress" in e.players[5].used
    before = len(e.events)
    drive(e._night_role(e.players[5]))
    assert len(e.events) == before


def test_twins_truthful_information_despite_vortox_and_victory_gate():
    e = game()
    drive(e._night_role(e.players[7]))
    evil, _good = e.twins
    notices = [v for v in e.events if v["kind"] == "information"][-2:]
    for v in notices:
        other = e.by_id[v["data"]["value"]["twin"]]
        assert v["data"]["ability"] == "evil_twin" and v["data"]["value"]["role"] == other.role
        assert v["audience"] == [v["data"]["player"]]
    e._kill(e.players[9], "execution")
    assert e.result is None
    e._kill(e.by_id[evil], "execution")
    assert e.result["winner"] == "good"


@pytest.mark.parametrize("already_dead", [True, False])
def test_executing_good_twin_loses_even_if_already_dead(already_dead):
    e = game()
    drive(e._night_role(e.players[7]))
    good = e.by_id[e.twins[1]]
    if already_dead:
        e._kill(good, "demon", e.players[9])
    assert not e.result
    e._execute(good)
    assert e.result["winner"] == "evil"


def test_two_alive_with_demon_wins_despite_twins():
    e = game()
    drive(e._night_role(e.players[7]))
    for p in e.players:
        p.alive = p.id in ("p7", "p9")
    e.check_victory()
    assert e.result["winner"] == "evil"


def test_vortox_no_execution_loses_but_dead_execution_counts():
    e = game()
    e.phase = "day"
    e.config.conversations.rounds = 0
    drive(e._day())
    assert e.result["winner"] == "evil"
    e = game()
    e.phase = "day"
    e.config.conversations.rounds = 0
    e.players[0].alive = False
    gen = e._day()
    first = next(gen)
    e._execute(e.players[0])
    drive_after(first, gen)
    assert e.executed_today and e.result is None


def drive_after(d, gen):
    try:
        while True:
            d = gen.send(d.options[0])
    except StopIteration:
        return


def test_witch_nomination_death_precedes_votes_and_uses_new_threshold():
    e = game()
    e.phase = "day"
    e.curse = ("p8", "p0")
    # Nine alive before curse: death changes majority from five to four.
    e.players[6].alive = False
    e.players[6].public_alive = False
    drive(e._nominate(e.players[0], e.players[1]), lambda d: {"type": "vote", "yes": True})
    assert not e.players[0].alive and not e.players[0].dead_vote
    vote = next(v for v in reversed(e.events) if v["kind"] == "vote")
    assert vote["data"]["votes"]["p0"] is True and vote["data"]["threshold"] == 4
    death = next(v for v in e.events if v["kind"] == "death" and v["data"]["player"] == "p0")
    assert death["seq"] < vote["seq"]


@pytest.mark.parametrize("cancel", ["dead_source", "three_alive", "impaired_source"])
def test_witch_curse_no_longer_kills_when_ability_inactive(cancel, monkeypatch):
    e = game()
    e.phase = "day"
    drive(e._night_role(e.players[8]), lambda d: {"type": "choose", "target": "p0"})
    if cancel == "dead_source":
        e.players[8].alive = False
    elif cancel == "three_alive":
        for p in e.players:
            p.alive = p.id in ("p0", "p8", "p9")
    else:
        monkeypatch.setattr(e, "impaired", lambda p: p.id == "p8")
    e._on_nomination(e.players[0])
    assert e.players[0].alive


def test_vortox_attack_and_information_are_private_until_dawn():
    e = game()
    drive(e._night_role(e.players[9]), lambda d: {"type": "choose", "target": "p6"})
    assert not e.players[6].alive and e.players[6].public_alive
    assert not any(v["kind"] in ("death", "information") for v in e.visible_events())
    assert any(v["kind"] == "information" for v in e.visible_events("p6"))
    assert not any(
        v["kind"] == "information" and v["data"].get("player") == "p6" for v in e.visible_events("p0")
    )


@pytest.mark.parametrize("seed", range(12))
def test_supported_roster_bounded_legal_game(seed):
    e = game(seed)
    e.day = 0
    e.phase = "setup"
    e.config.conversations.rounds = 0
    e.config.limits.max_days = 8
    rng = random.Random(seed)
    d = e.advance()
    turns = 0
    while d and not e.result and turns < 2000:
        assert d.options
        action = rng.choice(d.options)
        d.validate(action, 1500)
        d = e.advance(action)
        turns += 1
    assert e.result is not None


def test_configuration_refuses_unsupported_sv_rosters():
    config = game().config.model_dump()
    config["roles"][0] = "artist"
    with pytest.raises(ValueError):
        GameConfig.model_validate(config)
    config = game().config.model_dump()
    config["players"].pop()
    config["roles"] = None
    with pytest.raises(ValueError):
        GameConfig.model_validate(config)
