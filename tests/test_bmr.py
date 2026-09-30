"""BMR ability interactions and deterministic transport-free game survey."""

import random

import pytest

from clocktower.bmr import BadMoonRisingEngine
from clocktower.config import GameConfig, PlayerConfig, demo_config
from clocktower.roles import COUNTS, ROLES, SCRIPTS


def game(*roles):
    # Unit fixtures isolate abilities; full legal setup distributions are checked below.
    config = GameConfig.model_construct(
        script="bad_moon_rising",
        players=[PlayerConfig(id=f"p{i}", name=f"P{i}") for i in range(len(roles))],
        roles=list(roles),
        shuffle_roles=False,
    )
    e = BadMoonRisingEngine(config)
    e.day, e.phase = 2, "night"
    return e


def drive(gen, choose=lambda d: d.options[0]):
    try:
        d = next(gen)
        while True:
            assert d.options, d
            action = choose(d)
            d.validate(action, 1500)
            d = gen.send(action)
    except StopIteration as stop:
        return stop.value


def choose_target(index):
    return lambda d: next(a for a in d.options if a.get("target") == f"p{index}")


def test_courtier_duration_source_impairment_and_goon():
    e = game("courtier", "goon", "fool", "gambler", "assassin", "po")
    drive(e._night_role(e.players[0]), lambda d: {"type": "choose", "role": "goon"})
    assert e.impaired(e.players[0]) and not e.impaired(e.players[1])
    assert e.players[1].alignment == "good"
    e = game("courtier", "fool", "gambler", "professor", "assassin", "po")
    drive(e._night_role(e.players[0]), lambda d: {"type": "choose", "role": "po"})
    for day in (2, 3, 4):
        e.day = day
        assert e.impaired(e.players[-1])
    e.day = 5
    assert not e.impaired(e.players[-1])
    e.day = 2
    e.players[0].alive = False
    assert not e.impaired(e.players[-1])


def test_goon_first_choice_alignment_and_drunken_source():
    e = game("goon", "gambler", "fool", "professor", "assassin", "po")
    e._selected(e.players[5], e.players[0])
    assert e.players[0].alignment == "evil" and e.impaired(e.players[5])
    e._selected(e.players[1], e.players[0])
    assert e.players[0].alignment == "evil" and not e.impaired(e.players[1])


def test_sailor_self_drunk_and_sober_protection():
    e = game("sailor", "gambler", "fool", "professor", "assassin", "po")
    e._kill(e.players[0], "demon", e.players[-1])
    assert e.players[0].alive
    drive(e._night_role(e.players[0]), choose_target(0))
    assert e.impaired(e.players[0])
    e._kill(e.players[0], "demon", e.players[-1])
    assert not e.players[0].alive


@pytest.mark.parametrize("role", ["sailor", "fool", "goon"])
def test_assassin_overcomes_protection_including_goon(role):
    e = game(role, "gambler", "courtier", "professor", "assassin", "po")
    drive(e._night_role(e.players[4]), choose_target(0))
    assert not e.players[0].alive and "assassin" in e.players[4].used


def test_fool_first_death_only_and_poison_does_not_spend_ability():
    e = game("fool", "courtier", "gambler", "professor", "assassin", "po")
    e._kill(e.players[0], "demon", e.players[-1])
    assert e.players[0].alive
    e._kill(e.players[0], "demon", e.players[-1])
    assert not e.players[0].alive
    e._resurrect(e.players[0])
    assert "fool" not in e.players[0].used
    e._drunk(e.players[1], e.players[0], 2, "test")
    e._kill(e.players[0], "demon", e.players[-1])
    assert not e.players[0].alive
    assert "fool" not in e.players[0].used


def test_tea_lady_good_neighbors_and_source_impairment():
    e = game("gambler", "tea_lady", "professor", "courtier", "assassin", "po")
    e._kill(e.players[0], "demon", e.players[-1])
    assert e.players[0].alive
    e.players[2].changed_alignment = "evil"
    e._kill(e.players[0], "demon", e.players[-1])
    assert not e.players[0].alive


def test_innkeeper_protects_both_and_drinks_one_until_dusk():
    e = game("innkeeper", "gambler", "professor", "courtier", "assassin", "po")
    targets = iter([1, 2])
    drive(e._night_role(e.players[0]), lambda d: choose_target(next(targets))(d))
    assert sum(e.impaired(e.players[i]) for i in (1, 2)) == 1
    for i in (1, 2):
        e._kill(e.players[i], "demon", e.players[-1])
        assert e.players[i].alive
    e.phase = "day"
    e._kill(e.players[1], "execution")
    assert not e.players[1].alive


def test_advocate_alternates_targets_and_pacifist_only_good_executions():
    e = game("pacifist", "gambler", "professor", "courtier", "devils_advocate", "po")
    e.config.policy.pacifist_save = "always"
    e.phase = "day"
    e._execute(e.players[1])
    assert e.players[1].alive
    e.config.policy.pacifist_save = "never"
    drive(e._night_role(e.players[4]), choose_target(1))
    e._execute(e.players[1])
    assert e.players[1].alive
    gen = e._night_role(e.players[4])
    decision = next(gen)
    assert all(a["target"] != "p1" for a in decision.options)
    gen.close()
    e.players[4].alive = False
    e._execute(e.players[1])
    assert not e.players[1].alive


@pytest.mark.parametrize("correct", [True, False])
def test_gambler_guess(correct):
    e = game("gambler", "courtier", "professor", "exorcist", "assassin", "po")
    drive(
        e._night_role(e.players[0]),
        lambda d: {"type": "choose", "target": "p1", "role": "courtier" if correct else "po"},
    )
    assert e.players[0].alive is correct


def test_grandmother_information_and_linked_demon_death():
    e = game("grandmother", "gambler", "professor", "exorcist", "assassin", "po")
    e._grandmother(e.players[0])
    child = e.by_id[e.grandchildren["p0"]]
    assert child.alignment == "good"
    assert e.events[-1]["data"]["value"] == {"player": child.id, "role": child.role}
    e._kill(child, "demon", e.players[-1])
    assert not e.players[0].alive


def test_professor_resurrection_refreshes_townsfolk_not_outsider():
    e = game("professor", "fool", "tinker", "exorcist", "assassin", "po")
    e.players[1].alive = False
    e.players[1].dead_vote = False
    e.players[1].used.add("fool")
    drive(e._night_role(e.players[0]), choose_target(1))
    assert e.players[1].alive and e.players[1].dead_vote and not e.players[1].used
    assert "professor" in e.players[0].used
    e.players[0].used.clear()
    e.players[2].alive = False
    drive(e._night_role(e.players[0]), choose_target(2))
    assert not e.players[2].alive


def test_minstrel_execution_drinks_everyone_except_self_through_next_day():
    e = game("minstrel", "gambler", "professor", "exorcist", "assassin", "po")
    e.phase = "day"
    e._execute(e.players[4])
    assert not e.impaired(e.players[0]) and e.impaired(e.players[5])
    e.day = 3
    assert e.impaired(e.players[5])
    e.day = 4
    assert not e.impaired(e.players[5])


def test_gossip_true_vs_false_and_tinker_discretion(monkeypatch):
    e = game("gossip", "tinker", "professor", "exorcist", "assassin", "po")
    monkeypatch.setattr(e, "choice", lambda label, options: options[0])
    e._extra_day_action(e.players[0], {"type": "gossip", "role": "po"})
    drive(e._night_role(e.players[0]))
    assert not e.players[0].alive
    e = game("gossip", "tinker", "professor", "exorcist", "assassin", "po")
    e._extra_day_action(e.players[0], {"type": "gossip", "role": "pukka"})
    drive(e._night_role(e.players[0]))
    assert all(p.alive for p in e.players)
    monkeypatch.setattr(e, "choice", lambda label, options: options[-1])
    e.config.policy.tinker_death = "random"
    drive(e._night_role(e.players[1]))
    assert not e.players[1].alive


def test_moonchild_uses_alignment_at_choice_and_waits_until_public_death():
    e = game("moonchild", "gambler", "professor", "exorcist", "assassin", "po")
    e._kill(e.players[0], "demon", e.players[-1])
    drive(e._moonchoices())
    assert not e.moon_targets
    e.players[0].public_alive = False
    drive(e._moonchoices(), choose_target(1))
    e.players[1].changed_alignment = "evil"
    drive(e._night_role(e.players[0]))
    assert not e.players[1].alive


def test_lunatic_private_identity_and_harmless_choices():
    e = game("lunatic", "gambler", "professor", "exorcist", "assassin", "po")
    obs = e.observation("p0")
    assert obs["self"]["role"] == "po" and obs["self"]["alignment"] == "evil"
    assert e.players[0].alignment == "good"
    drive(e._night_role(e.players[0]), choose_target(1))
    assert e.players[1].alive
    info = e.events[-1]
    assert info["audience"] == ["p5"] and info["data"]["value"]["lunatic"] == "p0"


def test_pukka_delayed_poison_death_and_exorcism():
    e = game("gambler", "courtier", "professor", "exorcist", "assassin", "pukka")
    drive(e._night_role(e.players[-1]), choose_target(0))
    assert e.players[0].alive and e.impaired(e.players[0])
    e.day = 3
    e.exorcised = "p5"
    drive(e._night_role(e.players[-1]))
    assert not e.players[0].alive and not e.impaired(e.players[0])


def test_pukka_drunk_cannot_kill_and_poison_returns_when_sober():
    e = game("gambler", "courtier", "professor", "exorcist", "assassin", "pukka")
    drive(e._night_role(e.players[-1]), choose_target(0))
    e._drunk(e.players[1], e.players[-1], 3, "test")
    e.day = 3
    drive(e._night_role(e.players[-1]), choose_target(2))
    assert e.players[0].alive and not e.impaired(e.players[0])
    e.day = 4
    assert e.impaired(e.players[0])


def test_exorcist_stops_waking_and_cannot_repeat_target():
    e = game("exorcist", "gambler", "professor", "courtier", "assassin", "po")
    drive(e._night_role(e.players[0]), choose_target(5))
    drive(e._night_role(e.players[5]))
    assert "p5" not in e.woke and all(p.alive for p in e.players)
    gen = e._night_role(e.players[0])
    d = next(gen)
    assert all(a["target"] != "p5" for a in d.options)
    gen.close()


def test_po_drunk_charge_survives_exorcism_then_three_choices():
    e = game("gambler", "courtier", "professor", "exorcist", "assassin", "po")
    e._drunk(e.players[1], e.players[5], 2, "test")
    drive(e._night_role(e.players[5]), lambda d: {"type": "pass"})
    assert "p5" in e.po_charged
    e.day = 3
    e.exorcised = "p5"
    drive(e._night_role(e.players[5]))
    assert "p5" in e.po_charged
    e.day = 4
    e.exorcised = None
    targets = iter([0, 2, 3])
    drive(e._night_role(e.players[5]), lambda d: choose_target(next(targets))(d))
    assert all(not e.players[i].alive for i in (0, 2, 3)) and "p5" not in e.po_charged


def test_shabaloth_two_deaths_and_regurgitation(monkeypatch):
    e = game("gambler", "courtier", "professor", "exorcist", "assassin", "shabaloth")
    targets = iter([0, 2])
    drive(e._night_role(e.players[-1]), lambda d: choose_target(next(targets))(d))
    assert not e.players[0].alive and not e.players[2].alive
    e.day = 3
    e.config.policy.shabaloth_regurgitate = "always"
    e.exorcised = "p5"
    monkeypatch.setattr(e, "choice", lambda label, options: options[0])
    drive(e._night_role(e.players[-1]))
    assert e.players[0].alive and not e.players[2].alive


def test_zombuul_fake_death_vote_and_nomination_threshold():
    e = game("gambler", "courtier", "professor", "exorcist", "innkeeper", "assassin", "zombuul")
    e.phase = "day"
    zombie = e.players[-1]
    e._kill(zombie, "execution")
    assert zombie.alive and not e.socially_alive(zombie) and not e.result
    drive(e._nominate(e.players[0], e.players[1]), lambda d: {"type": "vote", "yes": True})
    vote = e.events[-1]["data"]
    assert vote["threshold"] == 3 and not zombie.dead_vote
    nominations = []

    def choose(d):
        if d.kind == "nomination":
            nominations.append(d.player)
        return d.options[0]

    drive(e._day(), choose)
    assert nominations and zombie.id not in nominations
    e._kill(zombie, "execution")
    assert e.result["winner"] == "good"


@pytest.mark.parametrize("execute_good", [True, False])
def test_mastermind_extra_day_result(execute_good):
    e = game("gambler", "courtier", "professor", "exorcist", "mastermind", "po")
    e.phase = "day"
    e._execute(e.players[-1])
    assert not e.result and e.mastermind_day == 3
    e.day = 3
    e._execute(e.players[0] if execute_good else e.players[4])
    assert e.result["winner"] == ("evil" if execute_good else "good")


def test_mastermind_no_execution_and_chambermaid_wakes():
    e = game("chambermaid", "courtier", "professor", "exorcist", "mastermind", "po")
    e.phase = "day"
    e._execute(e.players[-1])
    e.day = 3
    e.config.conversations.rounds = 0
    drive(e._day())
    assert e.result["winner"] == "good"
    e = game("chambermaid", "courtier", "professor", "exorcist", "assassin", "po")
    drive(e._night_role(e.players[1]), lambda d: {"type": "pass"})
    targets = iter([1, 2])
    drive(e._night_role(e.players[0]), lambda d: choose_target(next(targets))(d))
    assert e.events[-1]["data"]["value"] == 1


def test_godfather_information_and_outsider_trigger():
    e = game("moonchild", "gambler", "professor", "exorcist", "godfather", "po")
    e.day = 1
    drive(e._night_role(e.players[4]))
    assert e.events[-1]["data"]["value"] == {"outsiders": ["moonchild"]}
    e.day = 2
    drive(e._night_role(e.players[4]))
    assert all(p.alive for p in e.players)
    e.phase = "day"
    e._kill(e.players[0], "execution")
    e.phase = "night"
    drive(e._night_role(e.players[4]), choose_target(1))
    assert not e.players[1].alive


@pytest.mark.parametrize("count", range(5, 16))
def test_bmr_setup_and_offline_seed_survey(count):
    for seed in range(4):
        config = demo_config(count)
        config.script = "bad_moon_rising"
        config.seed = seed
        config.conversations.rounds = 0
        config.limits.max_days = 8
        e = BadMoonRisingEngine(config)
        assert len({p.role for p in e.players}) == count
        assert all(p.role in SCRIPTS["bad_moon_rising"].roles for p in e.players)
        expected = list(COUNTS[count])
        if any(p.role == "godfather" for p in e.players):
            expected[0] -= 1
            expected[1] += 1
        assert [
            sum(ROLES[p.role].team == t for p in e.players)
            for t in ("townsfolk", "outsider", "minion", "demon")
        ] == expected
        rng = random.Random(seed)
        d = e.advance()
        turns = 0
        while d and not e.result and turns < 2000:
            assert d.options
            action = rng.choice(d.options)
            d.validate(action, 1500)
            d = e.advance(action)
            turns += 1
        assert e.result is not None, (count, seed, turns)


@pytest.mark.parametrize("delta", [-1, 1])
def test_godfather_setup_adjustments(delta):
    for count in (6, 8, 9, 11, 12, 14, 15):
        for seed in range(12):
            config = demo_config(count)
            config.script = "bad_moon_rising"
            config.seed = seed
            config.policy.godfather_outsiders = delta
            e = BadMoonRisingEngine(config)
            expected = COUNTS[count][1] + (delta if any(p.role == "godfather" for p in e.players) else 0)
            assert sum(ROLES[p.role].team == "outsider" for p in e.players) == expected


@pytest.mark.parametrize("seed", [0, 3, 7])
async def test_normal_bmr_runner_archive_roundtrip(tmp_path, seed):
    from clocktower.archives import export_archive, import_archive
    from clocktower.runner import Runner
    from clocktower.storage import Store

    config = demo_config()
    config.script = "bad_moon_rising"
    config.seed = seed
    config.conversations.rounds = 0
    config.limits.max_days = 8
    runner = Runner(config, Store(tmp_path))
    assert isinstance(runner.engine, BadMoonRisingEngine)
    record = await runner.run()
    assert record["status"] in ("completed", "interrupted")
    assert record["turns"] > 0
    archive = export_archive(record)
    imported = import_archive(archive)
    assert imported["events"] == archive["run"]["events"]
    assert imported["config"]["script"] == "bad_moon_rising"


def test_source_effects_do_not_return_after_source_resurrection():
    e = game("courtier", "gambler", "innkeeper", "professor", "assassin", "pukka")
    drive(e._night_role(e.players[0]), lambda d: {"type": "choose", "role": "gambler"})
    assert e.impaired(e.players[1])
    e._kill(e.players[0], "assassin", e.players[4])
    e._resurrect(e.players[0])
    assert not e.impaired(e.players[1])
    targets = iter([1, 3])
    drive(e._night_role(e.players[2]), lambda d: choose_target(next(targets))(d))
    e._kill(e.players[2], "assassin", e.players[4])
    e._resurrect(e.players[2])
    assert e.inn_safe is None
    drive(e._night_role(e.players[-1]), choose_target(1))
    assert e.impaired(e.players[1])
    e._kill(e.players[-1], "assassin", e.players[4])
    e._resurrect(e.players[-1])
    assert not e.impaired(e.players[1])


def test_courtier_disabling_mastermind_ends_extra_day_immediately():
    e = game("courtier", "gambler", "professor", "exorcist", "mastermind", "po")
    e.phase = "day"
    e._execute(e.players[-1])
    assert not e.result
    drive(e._night(), lambda d: {"type": "choose", "role": "mastermind"})
    assert e.result["winner"] == "good"


def test_dawn_reports_final_life_state_after_resurrection_then_death():
    e = game("gambler", "courtier", "professor", "exorcist", "assassin", "po")
    target = e.players[0]
    target.alive = False
    target.public_alive = False
    e._resurrect(target)
    e._kill(target, "assassin", e.players[4])
    e._dawn_state()
    assert not target.public_alive
    assert target.id not in e.resurrected
    assert target.id in e.night_dead


def test_repeated_pukka_target_retains_new_poison_after_old_death():
    e = game("gambler", "courtier", "professor", "exorcist", "assassin", "pukka")
    drive(e._night_role(e.players[-1]), choose_target(0))
    e.day = 3
    drive(e._night_role(e.players[-1]), choose_target(0))
    assert not e.players[0].alive and e.impaired(e.players[0])
    assert e.pukka_target == "p0" and e.pukka_previous is None
    e.day = 4
    e.exorcised = "p5"
    drive(e._night_role(e.players[-1]))
    assert e.pukka_target is None and not e.impaired(e.players[0])
