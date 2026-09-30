import pytest

from clocktower.config import GameConfig, PlayerConfig, demo_config
from clocktower.engine import Engine
from clocktower.roles import COUNTS, ROLES


def game(roles):
    return Engine(
        GameConfig(
            players=[PlayerConfig(id=f"p{i}", name=f"P{i}") for i in range(len(roles))],
            roles=roles,
            shuffle_roles=False,
        )
    )


def drive(generator, choose):
    try:
        decision = next(generator)
        while True:
            decision = generator.send(choose(decision))
    except StopIteration as stop:
        return stop.value


@pytest.mark.parametrize("count", range(5, 16))
def test_setup_counts_and_unique_characters(count):
    for seed in range(10):
        config = demo_config(count)
        config.seed = seed
        engine = Engine(config)
        counts = [
            sum(ROLES[p.role].team == team for p in engine.players)
            for team in ("townsfolk", "outsider", "minion", "demon")
        ]
        expected = list(COUNTS[count])
        if any(p.role == "baron" for p in engine.players):
            expected[0] -= 2
            expected[1] += 2
        assert counts == expected
        assert len({p.role for p in engine.players}) == count
        assert len(engine.bluffs) == 3
        assert not set(engine.bluffs) & {p.shown_role for p in engine.players}


def test_soldier_poison_monk_and_expiry():
    e = game(["soldier", "monk", "chef", "poisoner", "imp"])
    soldier, monk, _, poisoner, imp = e.players
    e.phase = "night"
    e._demon_attack(soldier, imp)
    assert soldier.alive
    e.poison_source, e.poison_target = poisoner.id, soldier.id
    e.protector, e.protected = monk.id, soldier.id
    e._demon_attack(soldier, imp)
    assert soldier.alive
    e.protected = None
    e._demon_attack(soldier, imp)
    assert not soldier.alive


def test_drunk_has_shown_role_but_no_ability():
    e = game(["soldier", "chef", "drunk", "poisoner", "imp", "empath"])
    drunk = e.players[2]
    assert drunk.shown_role != "drunk" and e.impaired(drunk)
    obs = e.observation(drunk.id)
    assert obs["self"]["role"] == drunk.shown_role
    assert "drunk" not in str(obs)


def test_scarlet_woman_and_starpass_do_not_end_game():
    e = game(["chef", "soldier", "empath", "scarlet_woman", "imp"])
    e._kill(e.players[4], "execution")
    assert e.players[3].role == "imp" and not e.result
    e._kill(e.players[3], "execution")
    assert e.result["winner"] == "good"
    e = game(["chef", "soldier", "empath", "poisoner", "imp"])
    e.phase = "night"
    e._demon_attack(e.players[4], e.players[4])
    assert e.players[3].role == "imp" and not e.result


def test_saint_execution_and_poison():
    for poisoned in (False, True):
        e = game(["chef", "soldier", "empath", "saint", "poisoner", "imp"])
        if poisoned:
            e.poison_source, e.poison_target = "p4", "p3"
        e._execute(e.players[3])
        assert bool(e.result) != poisoned
        if e.result:
            assert e.result["winner"] == "evil"


def test_virgin_executes_townsfolk_immediately_and_only_once():
    e = game(["chef", "virgin", "empath", "poisoner", "imp"])
    e.phase = "day"
    assert drive(e._nominate(e.players[0], e.players[1]), lambda d: d.options[0]) is True
    assert not e.players[0].alive and e.executed == "p0"
    assert drive(e._nominate(e.players[2], e.players[1]), lambda d: d.options[0]) is False
    assert e.players[2].alive


def test_dead_vote_and_butler_master_gate():
    e = game(["chef", "soldier", "empath", "butler", "poisoner", "imp"])
    e.players[3].master = "p0"
    e.players[2].alive = False

    def vote(d):
        if d.player == "p3":
            assert d.options == [{"type": "vote", "yes": False}]
        return d.options[0] if d.player in ("p0", "p3") else d.options[-1]

    drive(e._nominate(e.players[0], e.players[1]), vote)
    assert not e.players[2].dead_vote
    seen = []
    drive(e._nominate(e.players[1], e.players[4]), lambda d: seen.append(d.player) or d.options[0])
    assert "p2" not in seen


def test_tied_vote_clears_block_but_retains_high_water_mark():
    e = game(["chef", "soldier", "empath", "poisoner", "imp"])
    vote = lambda d: {"type": "vote", "yes": d.player in ("p0", "p1", "p2")}
    drive(e._nominate(e.players[0], e.players[1]), vote)
    assert e.block == "p1" and e.high_votes == 3
    drive(e._nominate(e.players[1], e.players[2]), vote)
    assert e.block is None and e.high_votes == 3


def test_private_events_and_illegal_actions():
    e = game(["chef", "soldier", "empath", "poisoner", "imp"])
    d = e.advance()
    before = len(e.events)
    with pytest.raises(ValueError):
        e.advance({"type": "choose", "target": "nonexistent"})
    assert len(e.events) == before and e.pending == d
    e.emit("message", {"text": "whisper-secret"}, ["p0", "p1"])
    assert "whisper-secret" not in str(e.observation("p2"))
    assert "whisper-secret" not in str(e.visible_events())
    assert "whisper-secret" in str(e.observation("p0"))
    assert all(x["kind"] != "grimoire" for x in e.visible_events())


def test_mayor_no_execution_and_red_herring():
    e = game(["mayor", "fortune_teller", "chef", "poisoner", "imp"])
    e.players[2].alive = e.players[3].alive = False
    e.config.conversations.rounds = 0
    drive(e._day(), lambda d: d.options[0])
    assert e.result["winner"] == "good"
    e = game(["mayor", "fortune_teller", "chef", "poisoner", "imp"])
    e.red_herring = "p0"
    drive(e._night_role(e.players[1]), lambda d: {"type": "choose", "targets": ["p0", "p2"]})
    assert e.events[-1]["data"]["value"]["demon"] is True


def test_recluse_spy_registration_and_ravenkeeper():
    e = game(["chef", "ravenkeeper", "empath", "recluse", "spy", "imp"])
    e.config.policy.registration = "misregister"
    assert e.registered_evil(e.players[3]) is True
    assert e.registered_evil(e.players[4]) is False
    e.phase = "night"
    e._demon_attack(e.players[1], e.players[5])
    assert e.players[1].id in e.night_dead
    drive(e._night_role(e.players[1]), lambda d: {"type": "choose", "target": "p0"})
    assert e.events[-1]["data"]["value"]["role"] == "chef"


def test_washerwoman_when_only_townsfolk():
    e = game(["washerwoman", "saint", "recluse", "baron", "imp"])
    e._starting_info(e.players[0])
    info = e.events[-1]["data"]["value"]
    assert info["role"] == "washerwoman" and "p0" in info["players"]


def test_night_order_no_extra_starpass_attack_and_poison_ends():
    e = game(["chef", "soldier", "empath", "imp", "poisoner"])
    e.day = 1  # Exercise a subsequent night, with successor seated after Imp.
    decisions = []

    def choose(d):
        decisions.append(d.player)
        return {"type": "choose", "target": "p4" if d.player == "p4" else "p3"}

    drive(e._night(), choose)
    assert decisions == ["p4", "p3"]
    assert e.players[4].role == "imp"
    assert not e.impaired(e.players[4])
    assert len(e.night_dead) == 1


def test_first_night_order_and_teensyville_team_info():
    for count in (5, 7):
        e = Engine(demo_config(count))
        drive(e._night(), lambda d: d.options[0])
        team_info = [
            event
            for event in e.events
            if event["kind"] == "information"
            and isinstance(event["data"]["value"], dict)
            and "minions" in event["data"]["value"]
        ]
        assert bool(team_info) == (count >= 7)
        assert not any(event["kind"] == "death" for event in e.events)


def test_librarian_zero_and_undertaker_execution_identity():
    e = game(["librarian", "undertaker", "chef", "poisoner", "imp"])
    e._starting_info(e.players[0])
    assert e.events[-1]["data"]["value"] == {"count": 0}
    e.phase = "day"
    e._execute(e.players[2])
    drive(e._night_role(e.players[1]), lambda d: d.options[0])
    assert e.events[-1]["data"]["value"] == {"target": "p2", "role": "chef"}


def test_mayor_redirect_respects_soldier():
    e = game(["mayor", "soldier", "chef", "poisoner", "imp"])
    e.config.policy.mayor_bounce = "always"
    e.choice = lambda label, values: "p1"
    e._demon_attack(e.players[0], e.players[4])
    assert all(p.alive for p in e.players)


def test_poisoned_virgin_does_not_trigger_later():
    e = game(["virgin", "soldier", "chef", "poisoner", "imp"])
    e.poison_target, e.poison_source = "p0", "p3"
    drive(e._nominate(e.players[1], e.players[0]), lambda d: d.options[0])
    e.poison_target = None
    drive(e._nominate(e.players[2], e.players[0]), lambda d: d.options[0])
    assert e.players[1].alive and e.players[2].alive


def test_zero_conversations_still_allows_slayer():
    e = game(["slayer", "soldier", "chef", "poisoner", "imp"])
    e.config.conversations.rounds = 0
    e.phase = "day"

    def action(d):
        assert d.kind == "day_ability"
        return {"type": "slayer", "target": "p4"}

    drive(e._day(), action)
    assert e.result["winner"] == "good"


def test_vote_requires_json_boolean():
    from clocktower.engine import Decision

    decision = Decision("p0", "vote", "Vote", [{"type": "vote", "yes": False}])
    with pytest.raises(ValueError):
        decision.validate({"type": "vote", "yes": 0}, 100)


def test_scarlet_woman_day_change_not_disclosed_until_night():
    e = game(["slayer", "soldier", "chef", "scarlet_woman", "imp"])
    e.phase = "day"
    e.day = 1
    e._kill(e.players[4], "slayer", e.players[0])
    assert e.players[3].role == "imp"
    assert e.observation("p3")["self"]["role"] == "scarlet_woman"
    decision = next(e._night())
    assert decision.player == "p3"
    assert e.observation("p3")["self"]["role"] == "imp"


def test_butler_vote_menu_does_not_disclose_poisoning():
    for poisoned in (False, True):
        e = game(["chef", "soldier", "empath", "butler", "poisoner", "imp"])
        e.players[3].master = "p0"
        if poisoned:
            e.poison_source, e.poison_target = "p4", "p3"

        def vote(d):
            if d.player == "p3":
                assert d.options == [{"type": "vote", "yes": False}]
            return d.options[0]

        drive(e._nominate(e.players[0], e.players[1]), vote)
