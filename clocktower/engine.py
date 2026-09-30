"""Network-free authoritative Trouble Brewing state machine.

A generator describes timing; only ``advance`` accepts validated player input.
All random storyteller decisions use a private seeded RNG and are audit events.
"""

from __future__ import annotations

import copy
import itertools
import random
from collections.abc import Generator
from dataclasses import dataclass, field
from typing import Any

from .config import GameConfig
from .roles import COUNTS, MINIONS, OUTSIDERS, ROLES, SCRIPTS, TOWNSFOLK


@dataclass
class Player:
    id: str
    name: str
    role: str
    shown_role: str
    alive: bool = True
    public_alive: bool = True
    dead_vote: bool = True
    used: set[str] = field(default_factory=set)
    master: str | None = None
    changed_alignment: str | None = None

    @property
    def alignment(self) -> str:
        if self.changed_alignment:
            return self.changed_alignment
        return "evil" if ROLES[self.role].team in ("minion", "demon") else "good"


@dataclass
class Decision:
    player: str
    kind: str
    prompt: str
    options: list[dict[str, Any]]
    text: bool = False

    def validate(self, action: Any, max_chars: int) -> dict:
        if not isinstance(action, dict):
            raise ValueError("Action must be a JSON object")  # noqa: TRY004 - domain validation error
        base = {k: v for k, v in action.items() if k not in ("text", "notes")}
        if ("yes" in base and not isinstance(base["yes"], bool)) or base not in self.options:
            raise ValueError("Choose exactly one supplied legal action")
        if "text" in action and (
            not self.text or not isinstance(action["text"], str) or len(action["text"]) > max_chars
        ):
            raise ValueError("Invalid or overlong message text")
        if "notes" in action and (not isinstance(action["notes"], str) or len(action["notes"]) > 4000):
            raise ValueError("Notes must be a string of at most 4000 characters")
        return copy.deepcopy(action)


class Engine:
    def __init__(self, config: GameConfig):
        self.config = config
        self.rng = random.Random(config.seed)
        self.events: list[dict] = []
        self.day = 0
        self.phase = "setup"
        self.result: dict | None = None
        self.poison_target: str | None = None
        self.poison_source: str | None = None
        self.protected: str | None = None
        self.protector: str | None = None
        self.executed: str | None = None
        self.night_dead: list[str] = []
        self.pending_role_notifications: set[str] = set()
        self.block: str | None = None
        self.high_votes = 0
        self.nominated: set[str] = set()
        self.nominators: set[str] = set()
        roles = list(config.roles) if config.roles else self._draw_roles()
        if config.shuffle_roles:
            self.rng.shuffle(roles)
        self.players = [Player(p.id, p.name, r, r) for p, r in zip(config.players, roles)]
        self.by_id = {p.id: p for p in self.players}
        for p in self.players:
            if p.role == "drunk":
                p.shown_role = self.rng.choice([r for r in TOWNSFOLK if r not in roles])
        self._prepare_players()
        self.red_herring = self.rng.choice([p.id for p in self.players if p.alignment == "good"])
        self.bluffs = self.rng.sample(
            [
                r
                for r in SCRIPTS[self.config.script].roles
                if ROLES[r].team in ("townsfolk", "outsider")
                and r not in roles
                and r not in [p.shown_role for p in self.players]
            ],
            3,
        )
        self.emit(
            "setup",
            {
                "players": [{"id": p.id, "name": p.name} for p in self.players],
                "script": config.script,
                "base_counts": COUNTS[len(self.players)],
            },
        )
        self.emit("grimoire", self.grimoire(), [])
        for p in self.players:
            self.emit(
                "role", {"player": p.id, "role": p.shown_role, "alignment": self.shown_alignment(p)}, [p.id]
            )
        self.pending: Decision | None = None
        self._flow = self._game()

    def shown_alignment(self, p: Player) -> str:
        return p.alignment

    def _prepare_players(self):
        pass

    def _draw_roles(self) -> list[str]:
        towns, outsiders, minions, _ = COUNTS[len(self.config.players)]
        pool = SCRIPTS[self.config.script].roles
        teams = {
            team: [r for r in pool if ROLES[r].team == team]
            for team in ("townsfolk", "outsider", "minion", "demon")
        }
        selected = self.rng.sample(teams["minion"], minions)
        if "baron" in selected:
            towns -= 2
            outsiders += 2
        if "godfather" in selected:
            delta = self.config.policy.godfather_outsiders
            if outsiders + delta < 0:
                raise ValueError("Godfather cannot remove an Outsider from a zero-Outsider setup")
            towns -= delta
            outsiders += delta
        demons = teams["demon"]
        return (
            self.rng.sample(teams["townsfolk"], towns)
            + self.rng.sample(teams["outsider"], outsiders)
            + selected
            + [demons[0] if len(demons) == 1 else self.rng.choice(demons)]
        )

    def emit(self, kind: str, data: Any, audience: list[str] | None = None):
        self.events.append(
            {
                "seq": len(self.events) + 1,
                "day": self.day,
                "phase": self.phase,
                "kind": kind,
                "data": copy.deepcopy(data),
                "audience": audience,
            }
        )

    def grimoire(self) -> dict:
        return {
            "players": [
                {
                    "id": p.id,
                    "role": p.role,
                    "shown_role": p.shown_role,
                    "alive": p.alive,
                    "alignment": p.alignment,
                    "used": sorted(p.used),
                    "master": p.master,
                    "poisoned": self.impaired(p) and p.role != "drunk",
                }
                for p in self.players
            ],
            "red_herring": self.red_herring,
            "bluffs": self.bluffs,
            "protected": self.protected,
        }

    def impaired(self, p: Player) -> bool:
        # Poison lasts until dusk unless its living source loses its ability.
        return p.role == "drunk" or (
            p.id == self.poison_target
            and self.poison_source is not None
            and self.by_id[self.poison_source].alive
            and self.by_id[self.poison_source].role == "poisoner"
        )

    def functioning(self, p: Player) -> bool:
        return p.alive and not self.impaired(p)

    def living(self) -> list[Player]:
        return [p for p in self.players if p.alive]

    def role_player(self, role: str) -> Player | None:
        return next((p for p in self.players if p.role == role and p.alive), None)

    def choice(self, label: str, candidates: list[Any]) -> Any:
        chosen = self.rng.choice(candidates)
        self.emit("storyteller", {"decision": label, "choice": chosen}, [])
        return chosen

    def misregisters(self, p: Player) -> bool:
        if p.role not in ("spy", "recluse") or self.impaired(p):
            return False
        policy = self.config.policy.registration
        return policy == "misregister" or (policy == "random" and self.choice("registration", [True, False]))

    def registered_role(self, p: Player, requested_team: str | None = None) -> str:
        if self.misregisters(p):
            possibilities = TOWNSFOLK + OUTSIDERS if p.role == "spy" else MINIONS + ["imp"]
            if requested_team:
                possibilities = [r for r in possibilities if ROLES[r].team == requested_team]
            if possibilities:
                return self.choice("registered character", possibilities)
        return p.role

    def registered_evil(self, p: Player) -> bool:
        return (p.alignment == "good") if self.misregisters(p) else p.alignment == "evil"

    def info(self, p: Player, value: Any):
        self.emit("information", {"player": p.id, "ability": p.shown_role, "value": value}, [p.id])

    def _number_info(self, p: Player, value: int, maximum: int):
        if self.impaired(p) and self.config.policy.misinformation == "random":
            value = self.choice("impaired information", list(range(maximum + 1)))
        self.info(p, value)

    def _character_info(self, p: Player, target: Player):
        value = self.registered_role(target)
        if self.impaired(p) and self.config.policy.misinformation == "random":
            value = self.choice("impaired character information", list(SCRIPTS[self.config.script].roles))
        self.info(p, {"target": target.id, "role": value})

    def _starting_info(self, p: Player):
        team = {"washerwoman": "townsfolk", "librarian": "outsider", "investigator": "minion"}[p.shown_role]
        candidates = [(q, self.registered_role(q, team)) for q in self.players]
        candidates = [(q, r) for q, r in candidates if ROLES[r].team == team]
        other_candidates = [(q, r) for q, r in candidates if q != p]
        candidates = other_candidates or candidates
        impaired = self.impaired(p) and self.config.policy.misinformation == "random"
        if impaired:
            candidates = [
                (q, r)
                for q in self.players
                if q != p
                for r in SCRIPTS[self.config.script].roles
                if ROLES[r].team == team
            ]
        if not candidates:
            # A healthy Librarian can receive zero; the other roles always have a valid match.
            self.info(p, {"count": 0})
            return
        q, role = candidates[self.choice("starting information index", list(range(len(candidates))))]
        other = self.choice(
            "starting information decoy", [x.id for x in self.players if x.id != q.id and x != p]
        )
        pair = [q.id, other]
        self.rng.shuffle(pair)
        self.info(p, {"players": pair, "role": role})

    def advance(self, action: dict | None = None) -> Decision | None:
        if self.result:
            return None
        if self.pending:
            action = self.pending.validate(action, self.config.conversations.max_message_chars)
            self.emit(
                "action",
                {"player": self.pending.player, "kind": self.pending.kind, "action": action},
                [self.pending.player],
            )
            self.pending = None
            try:
                self.pending = self._flow.send(action)
            except StopIteration:
                pass
        else:
            try:
                self.pending = next(self._flow)
            except StopIteration:
                pass
        return self.pending

    def finish(self, winner: str, reason: str):
        if self.result is None:
            if self.phase == "night":
                for pid in self.night_dead:
                    self.by_id[pid].public_alive = False
                self.emit("dawn", {"deaths": self.night_dead})
            self.result = {"status": "completed", "winner": winner, "reason": reason}
            self.emit("result", self.result)

    def interrupt(self, reason: str):
        if self.result is None:
            self.result = {"status": "interrupted", "winner": None, "reason": reason}
            self.emit("result", self.result)

    def check_victory(self):
        if not any(p.alive and ROLES[p.role].team == "demon" for p in self.players):
            self.finish("good", "No living Demon remains")
        elif len(self.living()) <= 2:
            self.finish("evil", "Only two players remain alive")

    def _kill(self, target: Player, cause: str, source: Player | None = None):
        if not target.alive:
            return
        before = len(self.living())
        saint = target.role == "saint" and not self.impaired(target) and cause == "execution"
        is_demon = ROLES[target.role].team == "demon"
        scarlet = self.role_player("scarlet_woman")
        scarlet_works = scarlet is not None and self.functioning(scarlet) and before >= 5
        target.alive = False
        if self.phase == "night":
            self.night_dead.append(target.id)
            self.emit("death", {"player": target.id, "cause": cause}, [])
        else:
            target.public_alive = False
            self.emit("death", {"player": target.id, "cause": cause})
        if is_demon:
            successor = None
            if scarlet_works:
                successor = scarlet
            elif cause == "demon" and source is target:
                candidates = [q for q in self.living() if ROLES[q.role].team == "minion"]
                if candidates:
                    successor = (
                        candidates[0]
                        if self.config.policy.imp_successor == "first_seat"
                        else self.by_id[self.choice("Imp successor", [q.id for q in candidates])]
                    )
            if successor:
                successor.role = "imp"
                self.emit("transformation", {"player": successor.id, "role": "imp"}, [])
                if self.phase == "night":
                    successor.shown_role = "imp"
                    self.emit(
                        "role", {"player": successor.id, "role": "imp", "alignment": "evil"}, [successor.id]
                    )
                else:
                    self.pending_role_notifications.add(successor.id)
        if saint:
            self.finish("evil", "The Saint died by execution")
        self.check_victory()

    def _demon_attack(self, target: Player, source: Player):
        if not self.functioning(source) or not target.alive:
            return
        if target.role == "soldier" and self.functioning(target):
            return
        if target.id == self.protected and self.protector and self.functioning(self.by_id[self.protector]):
            return
        if target.role == "mayor" and self.functioning(target):
            bounce = self.config.policy.mayor_bounce
            if bounce == "always" or (bounce == "random" and self.choice("Mayor redirect", [True, False])):
                redirected = self.by_id[
                    self.choice("Mayor recipient", [q.id for q in self.players if q != target])
                ]
                # Redirected Demon deaths still respect Soldier and Monk protection.
                if redirected.role == "soldier" and self.functioning(redirected):
                    return
                if (
                    redirected.id == self.protected
                    and self.protector
                    and self.functioning(self.by_id[self.protector])
                ):
                    return
                self._kill(redirected, "demon", source)
                return
        self._kill(target, "demon", source)

    def _targets(self, exclude: str | None = None) -> list[dict]:
        return [{"type": "choose", "target": p.id} for p in self.players if p.id != exclude]

    def _night_role(self, p: Player) -> Generator[Decision, dict, None]:
        role = p.shown_role
        if role in ("poisoner", "monk", "imp", "butler", "ravenkeeper"):
            action = yield Decision(
                p.id,
                "night",
                ROLES[role].ability,
                self._targets(p.id if role in ("monk", "butler") else None),
            )
            target = self.by_id[action["target"]]
            if role == "ravenkeeper":
                self._character_info(p, target)
            elif role == "butler":
                p.master = target.id
            elif self.functioning(p):
                if role == "poisoner":
                    self.poison_target, self.poison_source = target.id, p.id
                elif role == "monk":
                    self.protected, self.protector = target.id, p.id
                elif role == "imp":
                    self._demon_attack(target, p)
        elif role in ("washerwoman", "librarian", "investigator"):
            self._starting_info(p)
        elif role == "chef":
            evils = [self.registered_evil(q) for q in self.players]
            self._number_info(
                p, sum(evils[i] and evils[(i + 1) % len(evils)] for i in range(len(evils))), len(self.players)
            )
        elif role == "empath":
            seat = self.players.index(p)
            neighbours = []
            for direction in (-1, 1):
                for step in range(1, len(self.players)):
                    q = self.players[(seat + direction * step) % len(self.players)]
                    if q.alive:
                        neighbours.append(q)
                        break
            self._number_info(p, sum(self.registered_evil(q) for q in neighbours), 2)
        elif role == "fortune_teller":
            action = yield Decision(
                p.id,
                "night",
                ROLES[role].ability,
                [{"type": "choose", "targets": list(pair)} for pair in itertools.combinations(self.by_id, 2)],
            )
            value = any(
                q == self.red_herring or self.registered_role(self.by_id[q], "demon") == "imp"
                for q in action["targets"]
            )
            if self.impaired(p) and self.config.policy.misinformation == "random":
                value = self.choice("impaired Fortune Teller", [True, False])
            self.info(p, {"targets": action["targets"], "demon": value})
        elif role == "undertaker" and self.executed:
            self._character_info(p, self.by_id[self.executed])
        elif role == "spy":
            if self.impaired(p):
                # An impaired Spy may legally receive a truthful Grimoire.
                self.emit("storyteller", {"decision": "impaired Spy", "choice": "truthful Grimoire"}, [])
            self.info(p, self.grimoire())

    def _night(self) -> Generator[Decision, dict, None]:
        self.phase = "night"
        self.day += 1
        self.night_dead = []
        self.poison_source = self.poison_target = self.protected = self.protector = None
        self.emit("phase", {"phase": "night", "day": self.day})
        for pid in self.pending_role_notifications:
            p = self.by_id[pid]
            p.shown_role = p.role
            self.emit("role", {"player": pid, "role": p.role, "alignment": p.alignment}, [pid])
        self.pending_role_notifications.clear()
        if self.day == 1 and len(self.players) >= 7:
            demon = self.role_player("imp")
            minions = [p.id for p in self.players if ROLES[p.role].team == "minion"]
            if demon:
                self.info(demon, {"minions": minions, "bluffs": self.bluffs})
                for pid in minions:
                    self.info(
                        self.by_id[pid], {"demon": demon.id, "minions": [m for m in minions if m != pid]}
                    )
        script = SCRIPTS[self.config.script]
        for role in script.first_night if self.day == 1 else script.other_nights:
            for p in [q for q in self.players if q.shown_role == role]:
                if p.shown_role != role:
                    continue
                if role == "ravenkeeper":
                    if p.id not in self.night_dead:
                        continue
                elif not p.alive:
                    continue
                yield from self._night_role(p)
                if self.result:
                    return
        self.emit("grimoire", self.grimoire(), [])
        self.phase = "day"
        self.emit("phase", {"phase": "day", "day": self.day})
        for pid in self.night_dead:
            self.by_id[pid].public_alive = False
        self.emit("dawn", {"deaths": self.night_dead})

    def _execute(self, target: Player):
        self.emit("execution", {"player": target.id})
        if target.alive:
            self.executed = target.id
            self._kill(target, "execution")

    def _nominate(self, nominator: Player, target: Player) -> Generator[Decision, dict, bool]:
        self.nominators.add(nominator.id)
        self.nominated.add(target.id)
        self.emit("nomination", {"nominator": nominator.id, "nominee": target.id})
        self._on_nomination(nominator)
        if self.result:
            return True
        if target.role == "virgin" and "virgin" not in target.used and target.alive:
            target.used.add("virgin")
            if (
                self.functioning(target)
                and ROLES[self.registered_role(nominator, "townsfolk")].team == "townsfolk"
            ):
                self._execute(nominator)
                return True
        votes: dict[str, bool] = {}
        seat = self.players.index(target)
        order = self.players[seat + 1 :] + self.players[: seat + 1]
        # Players raise hands together; obtain master's intention before the Butler.
        order.sort(key=lambda q: q.role == "butler" and q.alive)
        for p in order:
            if not self.socially_alive(p) and not p.dead_vote:
                votes[p.id] = False
                continue
            allowed = p.role != "butler" or not p.alive or bool(votes.get(p.master or "", False))
            options = [{"type": "vote", "yes": False}]
            if allowed:
                options.append({"type": "vote", "yes": True})
            vote = yield Decision(
                p.id,
                "vote",
                f"Vote on executing {target.name}. Living threshold: {(sum(self.socially_alive(q) for q in self.players) + 1) // 2}. Dead votes can be used once.",
                options,
            )
            votes[p.id] = vote["yes"]
            if vote["yes"] and not self.socially_alive(p):
                p.dead_vote = False
        tally = sum(votes.values())
        threshold = (sum(self.socially_alive(q) for q in self.players) + 1) // 2
        if tally >= threshold and tally > self.high_votes:
            self.block, self.high_votes = target.id, tally
        elif tally >= threshold and tally == self.high_votes:
            self.block = None
        self.emit(
            "vote",
            {
                "nominee": target.id,
                "votes": votes,
                "tally": tally,
                "threshold": threshold,
                "block": self.block,
                "high_votes": self.high_votes,
            },
        )
        return False

    def _on_nomination(self, nominator: Player):
        pass

    def _extra_day_options(self, p: Player) -> list[dict]:
        return []

    def _extra_day_action(self, p: Player, action: dict):
        pass

    def socially_alive(self, p: Player) -> bool:
        return p.alive

    def _day(self) -> Generator[Decision, dict, None]:
        self.executed = None
        self.block, self.high_votes = None, 0
        self.nominated, self.nominators = set(), set()
        for _ in range(max(1, self.config.conversations.rounds)):
            for p in self.players:
                talking = self.config.conversations.rounds > 0
                options = [{"type": "pass"}] + ([{"type": "speak"}] if talking else [])
                if talking and self.config.conversations.whispers:
                    options += [{"type": "whisper", "target": q.id} for q in self.players if q != p]
                if self.config.script == "trouble_brewing" and p.alive and "slayer" not in p.used:
                    options += [{"type": "slayer", "target": q.id} for q in self.players]
                options.extend(self._extra_day_options(p))
                action = yield Decision(
                    p.id,
                    "conversation" if talking else "day_ability",
                    (
                        "Speak, whisper, publicly gossip, or pass."
                        if self.config.script == "bad_moon_rising"
                        else "Speak, whisper, or pass." if self.config.script == "sects_and_violets"
                        else "Speak, whisper, claim a Slayer shot, or pass."
                    )
                    if talking
                    else "Use an available day ability or pass.",
                    options,
                    talking,
                )
                kind = action["type"]
                if kind in ("speak", "whisper"):
                    audience = [p.id, action["target"]] if kind == "whisper" else None
                    self.emit(
                        "message",
                        {"player": p.id, "target": action.get("target"), "text": action.get("text", "")},
                        audience,
                    )
                elif kind not in ("pass", "slayer"):
                    self._extra_day_action(p, action)
                elif kind == "slayer":
                    p.used.add("slayer")
                    target = self.by_id[action["target"]]
                    self.emit("slayer", {"player": p.id, "target": target.id})
                    if (
                        p.role == "slayer"
                        and self.functioning(p)
                        and self.registered_role(target, "demon") == "imp"
                    ):
                        self._kill(target, "slayer", p)
                    if self.result:
                        return
        # Each living player gets one nomination opportunity; passing doesn't consume a nomination.
        # Repeat rounds while somebody nominates, so players can respond to a later case.
        while not self.result:
            progress = False
            for p in self.players:
                if not self.socially_alive(p) or p.id in self.nominators:
                    continue
                options = [{"type": "pass"}] + [
                    {"type": "nominate", "target": q.id} for q in self.players if q.id not in self.nominated
                ]
                action = yield Decision(
                    p.id, "nomination", "Nominate any not-yet-nominated player, or pass.", options
                )
                if action["type"] == "nominate":
                    progress = True
                    ended = yield from self._nominate(p, self.by_id[action["target"]])
                    if ended or self.result:
                        return
            if not progress:
                break
        if self.block:
            self._execute(self.by_id[self.block])
        else:
            self.emit("no_execution", {})
            mayor = self.role_player("mayor")
            if mayor and self.functioning(mayor) and len(self.living()) == 3:
                self.finish("good", "Three players lived and the Mayor prevented an execution")
        self.check_victory()

    def _game(self) -> Generator[Decision, dict, None]:
        while not self.result:
            if self.day >= self.config.limits.max_days:
                self.interrupt("Day limit reached")
                return
            yield from self._night()
            if self.result:
                return
            yield from self._day()

    def visible_events(self, viewer: str = "public") -> list[dict]:
        if viewer not in ("public", "omniscient") and viewer not in self.by_id:
            raise ValueError("Unknown viewer")
        events = [
            e
            for e in self.events
            if viewer == "omniscient" or e["audience"] is None or viewer in e["audience"]
        ]
        # Reindex so hidden event counts cannot be inferred from sequence gaps.
        return [{**copy.deepcopy(e), "seq": i + 1, "audience": None} for i, e in enumerate(events)]

    def observation(self, player: str) -> dict:
        p = self.by_id[player]
        return {
            "self": {
                "id": p.id,
                "role": p.shown_role,
                "alignment": p.alignment,
                "ability": ROLES[p.shown_role].ability,
            },
            "players": [
                {"id": q.id, "name": q.name, "alive": q.public_alive, "dead_vote": q.dead_vote}
                for q in self.players
            ],
            "day": self.day,
            "phase": self.phase,
            "block": self.block,
            "events": self.visible_events(player),
        }
