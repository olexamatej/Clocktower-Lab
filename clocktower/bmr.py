"""Bad Moon Rising rules on the shared observation/decision/event engine.

Storyteller discretionary choices are seeded and private. Gossip uses explicit,
truth-evaluable statements rather than guessing whether free-form prose is true.
"""

from collections.abc import Generator
from dataclasses import dataclass

from .config import GameConfig
from .engine import Decision, Engine, Player
from .roles import COUNTS, ROLES, SCRIPTS


@dataclass
class Effect:
    source: str
    target: str
    until: int  # Last day; expires at the following dusk.
    kind: str


class BadMoonRisingEngine(Engine):
    def __init__(self, config: GameConfig):
        self.effects: list[Effect] = []
        self.inn_safe: tuple[str, list[str]] | None = None
        self.advocate: tuple[str, str] | None = None
        self.last_choices: dict[str, str] = {}
        self.grandchildren: dict[str, str] = {}
        self.pukka_target: str | None = None
        self.pukka_source: str | None = None
        self.pukka_previous: str | None = None
        self.po_charged: set[str] = set()
        self.shabaloth_targets: list[str] = []
        self.exorcised: str | None = None
        self.woke: set[str] = set()
        self.goon_triggered = False
        self.died_today = False
        self.outsider_died_today = False
        self.mastermind_day: int | None = None
        self.mastermind_source: str | None = None
        self.gossips: dict[str, bool] = {}
        self.moon_pending: set[str] = set()
        self.moon_targets: list[tuple[str, str, bool]] = []
        self.resurrected: list[str] = []
        super().__init__(config)

    def _prepare_players(self):
        demon = next(p for p in self.players if ROLES[p.role].team == "demon")
        for p in self.players:
            if p.role == "lunatic":
                p.shown_role = demon.role

    def shown_alignment(self, p: Player) -> str:
        return "evil" if p.role == "lunatic" else p.alignment

    def impaired(self, p: Player, visiting: set[str] | None = None) -> bool:
        seen = set(visiting or ())
        if p.id in seen:
            return False
        seen.add(p.id)
        for effect in self.effects:
            if effect.target != p.id or effect.until < self.day:
                continue
            source = self.by_id.get(effect.source)
            if source and source.alive and (source is p or not self.impaired(source, seen)):
                return True
        if p.id in (self.pukka_target, self.pukka_previous) and self.pukka_source:
            source = self.by_id[self.pukka_source]
            if source.alive and (source is p or not self.impaired(source, seen)):
                return True
        return False

    def _drunk(self, source: Player, target: Player, until: int, kind: str):
        self.effects.append(Effect(source.id, target.id, until, kind))
        self.emit(
            "storyteller", {"decision": kind, "source": source.id, "target": target.id, "until": until}, []
        )

    def socially_alive(self, p: Player) -> bool:
        return p.alive and not (p.role == "zombuul" and "zombuul" in p.used)

    def grimoire(self) -> dict:
        result = super().grimoire()
        for item in result["players"]:
            p = self.by_id[item["id"]]
            item["alive"] = self.socially_alive(p)
            item["actually_alive"] = p.alive
        return result

    def observation(self, player: str) -> dict:
        result = super().observation(player)
        if self.by_id[player].role == "lunatic":
            result["self"]["alignment"] = "evil"
        return result

    def _choose(
        self, p: Player, options: list[dict], prompt: str | None = None
    ) -> Generator[Decision, dict, dict]:
        self.woke.add(p.id)
        action = yield Decision(p.id, "night", prompt or ROLES[p.shown_role].ability, options)
        return action

    def _selected(self, source: Player, target: Player):
        if target.role == "goon" and self.functioning(target) and not self.goon_triggered:
            self.goon_triggered = True
            self._drunk(target, source, self.day, "Goon")
            if target.alignment != source.alignment:
                target.changed_alignment = source.alignment
                self.emit("alignment", {"player": target.id, "alignment": target.alignment}, [target.id])

    def _alive_targets(self, exclude: str | None = None) -> list[dict]:
        return [
            {"type": "choose", "target": p.id}
            for p in self.players
            if self.socially_alive(p) and p.id != exclude
        ]

    def _neighbors(self, p: Player) -> list[Player]:
        others = [q for q in self.players if q is not p and self.socially_alive(q)]
        if len(others) < 2:
            return others
        seat = self.players.index(p)
        clockwise = self.players[seat + 1 :] + self.players[:seat]
        return [
            next(q for q in clockwise if q in others),
            next(q for q in reversed(clockwise) if q in others),
        ]

    def _protected(self, target: Player, cause: str) -> bool:
        if target.role == "sailor" and self.functioning(target):
            return True
        for tea in self.players:
            if tea.role == "tea_lady" and self.functioning(tea):
                neighbors = self._neighbors(tea)
                if (
                    len(neighbors) == 2
                    and target in neighbors
                    and all(p.alignment == "good" for p in neighbors)
                ):
                    return True
        if self.phase == "night" and self.inn_safe:
            source, targets = self.inn_safe
            if target.id in targets and self.functioning(self.by_id[source]):
                return True
        if cause == "execution":
            if (
                self.advocate
                and self.advocate[1] == target.id
                and self.functioning(self.by_id[self.advocate[0]])
            ):
                return True
            pacifist = self.role_player("pacifist")
            if pacifist and self.functioning(pacifist) and target.alignment == "good":
                policy = self.config.policy.pacifist_save
                if policy == "always" or (policy == "random" and self.choice("Pacifist save", [False, True])):
                    return True
        if target.role == "fool" and "fool" not in target.used and self.functioning(target):
            target.used.add("fool")
            return True
        return False

    def _kill(self, target: Player, cause: str, source: Player | None = None):
        if not target.alive or self.result:
            return
        if cause != "assassin" and self._protected(target, cause):
            return
        healthy = not self.impaired(target)
        if target.role == "zombuul" and "zombuul" not in target.used and healthy and cause != "assassin":
            target.used.add("zombuul")
        else:
            target.alive = False
        if not target.alive:
            # Death ends effects; resurrection must not restore an earlier ability instance.
            self.effects = [effect for effect in self.effects if effect.source != target.id]
            if self.inn_safe and self.inn_safe[0] == target.id:
                self.inn_safe = None
            if self.advocate and self.advocate[0] == target.id:
                self.advocate = None
            if self.pukka_source == target.id:
                self.pukka_target = self.pukka_previous = self.pukka_source = None
        if self.phase == "night":
            if target.id not in self.night_dead:
                self.night_dead.append(target.id)
            self.emit("death", {"player": target.id, "cause": cause}, [])
        else:
            target.public_alive = False
            self.died_today = True
            if ROLES[target.role].team == "outsider":
                self.outsider_died_today = True
            self.emit("death", {"player": target.id, "cause": cause})
        if target.role == "moonchild" and "moonchild" not in target.used:
            self.moon_pending.add(target.id)
        if cause == "execution" and not target.alive:
            if ROLES[target.role].team == "minion":
                minstrel = self.role_player("minstrel")
                if minstrel and self.functioning(minstrel):
                    for p in self.players:
                        if p is not minstrel:
                            self._drunk(minstrel, p, self.day + 1, "Minstrel")
            if ROLES[target.role].team == "demon":
                mastermind = self.role_player("mastermind")
                if mastermind and self.functioning(mastermind):
                    self.mastermind_source = mastermind.id
                    self.mastermind_day = self.day + 1
        if cause == "demon" and not target.alive:
            for grandmother, grandchild in list(self.grandchildren.items()):
                gm = self.by_id[grandmother]
                if grandchild == target.id and self.functioning(gm):
                    self._kill(gm, "grandmother", source)
        self.emit("grimoire", self.grimoire(), [])
        self.check_victory()

    def _dawn_state(self):
        # A player resurrected and then killed again must not be announced alive.
        self.resurrected = list(dict.fromkeys(pid for pid in self.resurrected if self.socially_alive(self.by_id[pid])))
        self.night_dead = list(dict.fromkeys(pid for pid in self.night_dead if not self.socially_alive(self.by_id[pid])))

    def finish(self, winner: str, reason: str):
        already_finished = self.result is not None
        if self.phase == "night":
            self._dawn_state()
        super().finish(winner, reason)
        if not already_finished and self.phase == "night":
            for pid in self.resurrected:
                self.by_id[pid].public_alive = self.socially_alive(self.by_id[pid])
            for event in reversed(self.events):
                if event["kind"] == "dawn":
                    event["data"]["resurrected"] = list(self.resurrected)
                    break

    def check_victory(self):
        if self.mastermind_day is not None and self.mastermind_source:
            source = self.by_id[self.mastermind_source]
            if self.functioning(source):
                return
            self.mastermind_day = None
        super().check_victory()

    def _execute(self, target: Player):
        self.emit("execution", {"player": target.id})
        if self.mastermind_day == self.day:
            self.finish(
                "evil" if target.alignment == "good" else "good",
                "Mastermind: the executed player's team loses",
            )
            return
        if target.alive:
            before = target.alive
            self._kill(target, "execution")
            if before and not target.alive:
                self.executed = target.id
        if target.alive and self.socially_alive(target):
            self.emit("survived", {"player": target.id})

    def _resurrect(self, p: Player):
        if p.alive:
            return
        p.alive, p.dead_vote = True, True
        p.used.clear()
        self.resurrected.append(p.id)
        self.emit("resurrection", {"player": p.id}, [])
        self.moon_pending.discard(p.id)
        self.moon_targets = [v for v in self.moon_targets if v[0] != p.id]
        if p.role == "grandmother":
            self._grandmother(p)
        if p.role == "godfather":
            self.woke.add(p.id)
            self.info(p, {"outsiders": [q.role for q in self.players if ROLES[q.role].team == "outsider"]})

    def _grandmother(self, p: Player):
        self.woke.add(p.id)
        candidates = [q for q in self.players if q is not p and q.alignment == "good"]
        target = self.by_id[self.choice("Grandchild", [q.id for q in candidates])]
        if self.functioning(p):
            self.grandchildren[p.id] = target.id
        role = target.role
        if self.impaired(p):
            role = self.choice("Impaired Grandmother", list(SCRIPTS[self.config.script].roles))
        self.info(p, {"player": target.id, "role": role})

    def _night_role(self, p: Player) -> Generator[Decision, dict, None]:
        role = p.role
        if role == "grandmother":
            self._grandmother(p)
        elif role == "godfather" and self.day == 1:
            self.woke.add(p.id)
            outsiders = [q.role for q in self.players if ROLES[q.role].team == "outsider"]
            if self.impaired(p):
                outsiders = []
            self.info(p, {"outsiders": outsiders})
        elif role in ("sailor", "devils_advocate", "exorcist", "godfather"):
            if role == "godfather" and not self.outsider_died_today:
                return
            options = self._alive_targets() if role in ("sailor", "devils_advocate") else self._targets()
            if role in ("devils_advocate", "exorcist"):
                options = [a for a in options if a["target"] != self.last_choices.get(p.id)]
            if not options:
                return
            action = yield from self._choose(p, options)
            q = self.by_id[action["target"]]
            self.last_choices[p.id] = q.id
            self._selected(p, q)
            if self.functioning(p):
                if role == "sailor":
                    drunk = self.by_id[self.choice("Sailor drink", list(dict.fromkeys([p.id, q.id])))]
                    self._drunk(p, drunk, self.day, "Sailor")
                elif role == "devils_advocate":
                    self.advocate = (p.id, q.id)
                elif role == "exorcist" and ROLES[q.role].team == "demon":
                    self.exorcised = q.id
                    self.info(q, {"exorcist": p.id, "message": "You do not wake to attack tonight"})
                elif role == "godfather":
                    self._kill(q, "godfather", p)
        elif role == "courtier" and "courtier" not in p.used:
            action = yield from self._choose(
                p,
                [{"type": "pass"}]
                + [{"type": "choose", "role": r} for r in SCRIPTS[self.config.script].roles],
            )
            if action["type"] == "choose":
                p.used.add("courtier")
                chosen_role_target = next((q for q in self.players if q.role == action["role"]), None)
                if chosen_role_target:
                    self._selected(p, chosen_role_target)
                    if self.functioning(p):
                        self._drunk(p, chosen_role_target, self.day + 2, "Courtier")
        elif role in ("innkeeper", "chambermaid"):
            candidates = [
                q for q in self.players if role == "innkeeper" or (q is not p and self.socially_alive(q))
            ]
            if len(candidates) < 2:
                return
            a = yield from self._choose(
                p,
                [{"type": "choose", "target": q.id} for q in candidates],
                f"{ROLES[role].ability} Choose the first player.",
            )
            b = yield from self._choose(
                p,
                [{"type": "choose", "target": q.id} for q in candidates if q.id != a["target"]],
                "Choose the second, different player.",
            )
            targets = [a["target"], b["target"]]
            for target in targets:
                self._selected(p, self.by_id[target])
            if role == "innkeeper" and self.functioning(p):
                self.inn_safe = (p.id, targets)
                self._drunk(p, self.by_id[self.choice("Innkeeper drunk", targets)], self.day, "Innkeeper")
            elif role == "chambermaid":
                value = sum(target in self.woke for target in targets)
                self._number_info(p, value, 2)
        elif role == "gambler":
            action = yield from self._choose(
                p,
                [
                    {"type": "choose", "target": q.id, "role": r}
                    for q in self.players
                    for r in SCRIPTS[self.config.script].roles
                ],
            )
            q = self.by_id[action["target"]]
            self._selected(p, q)
            if self.functioning(p) and q.role != action["role"]:
                self._kill(p, "gambler", p)
        elif role in ("professor", "assassin") and role not in p.used:
            choices = (
                self._targets()
                if role == "assassin"
                else [{"type": "choose", "target": q.id} for q in self.players if not self.socially_alive(q)]
            )
            action = yield from self._choose(p, [{"type": "pass"}] + choices)
            if action["type"] == "choose":
                p.used.add(role)
                q = self.by_id[action["target"]]
                works = self.functioning(p)
                self._selected(p, q)
                if role == "assassin" and works:
                    self._kill(q, "assassin", p)
                elif role == "professor" and self.functioning(p) and ROLES[q.role].team == "townsfolk":
                    self._resurrect(q)
        elif role == "lunatic":
            yield from self._demon_turn(p, pretend=True)
        elif ROLES[role].team == "demon":
            yield from self._demon_turn(p)
        elif role == "gossip" and self.gossips.get(p.id) and self.functioning(p):
            gossip_candidates = [q.id for q in self.players if q.alive]
            if gossip_candidates:
                self._kill(self.by_id[self.choice("Gossip victim", gossip_candidates)], "gossip", p)
        elif role == "moonchild":
            for source, target, was_good in self.moon_targets:
                if source == p.id and was_good and not self.impaired(p):
                    self._kill(self.by_id[target], "moonchild", p)
        elif (
            role == "tinker"
            and self.config.policy.tinker_death == "random"
            and len(self.living()) > 3
            and self.functioning(p)
            and self.choice("Tinker death", [False, False, False, True])
        ):
            self._kill(p, "tinker", p)

    def _demon_turn(self, p: Player, pretend: bool = False) -> Generator[Decision, dict, None]:
        role = p.shown_role if pretend else p.role
        old = self.pukka_target if role == "pukka" and not pretend else None
        if role == "pukka" and not pretend:
            self.pukka_previous = old
        if role == "shabaloth" and not pretend:
            policy = self.config.policy.shabaloth_regurgitate
            candidates = [pid for pid in self.shabaloth_targets if not self.by_id[pid].alive]
            if (
                candidates
                and self.functioning(p)
                and (
                    policy == "always"
                    or (policy == "random" and self.choice("Regurgitate", [False, False, True]))
                )
            ):
                self._resurrect(self.by_id[self.choice("Regurgitated player", candidates)])
            self.shabaloth_targets = []
        acts = not (p.id == self.exorcised or (role == "zombuul" and self.died_today))
        if self.day == 1 and role != "pukka":
            acts = False
        targets: list[str] = []
        newly_poisoned = False
        if acts:
            count = 2 if role == "shabaloth" else 3 if role == "po" and p.id in self.po_charged else 1
            for index in range(count):
                options = [a for a in self._targets() if a["target"] not in targets]
                if role == "po" and count == 1:
                    options = [{"type": "pass"}] + options
                action = yield from self._choose(
                    p, options, f"{ROLES[role].ability} Choice {index + 1} of {count}."
                )
                if action["type"] == "pass":
                    self.po_charged.add(p.id)
                    break
                if role == "po":
                    self.po_charged.discard(p.id)
                target = self.by_id[action["target"]]
                targets.append(target.id)
                self._selected(p, target)
                if not pretend and self.functioning(p):
                    if role == "pukka":
                        self.pukka_target, self.pukka_source = target.id, p.id
                        newly_poisoned = True
                    else:
                        self._kill(target, "demon", p)
                if self.result:
                    return
        if pretend:
            if targets and self.functioning(p):
                for demon in self.players:
                    if demon.alive and ROLES[demon.role].team == "demon":
                        self.info(demon, {"lunatic": p.id, "targets": targets})
        elif role == "pukka" and old and self.functioning(p):
            # The old poison remains through the old victim's death, even when a new target is chosen.
            current = self.pukka_target
            self._kill(self.by_id[old], "demon", p)
            self.pukka_target = current if newly_poisoned else None
            self.pukka_previous = None
        elif role == "shabaloth" and self.functioning(p):
            self.shabaloth_targets = targets

    def _night(self) -> Generator[Decision, dict, None]:
        self.phase = "night"
        self.day += 1
        self.night_dead, self.resurrected = [], []
        self.effects = [e for e in self.effects if e.until >= self.day]
        self.inn_safe, self.advocate, self.exorcised = None, None, None
        self.goon_triggered = False
        self.woke.clear()
        self.emit("phase", {"phase": "night", "day": self.day})
        if self.day == 1:
            demon = next(p for p in self.players if ROLES[p.role].team == "demon")
            minions = [p.id for p in self.players if ROLES[p.role].team == "minion"]
            lunatic = self.role_player("lunatic")
            if len(self.players) >= 7:
                self.info(demon, {"minions": minions, "bluffs": self.bluffs})
                for pid in minions:
                    self.info(
                        self.by_id[pid], {"demon": demon.id, "minions": [m for m in minions if m != pid]}
                    )
                if lunatic:
                    fake = self.rng.sample(
                        [q.id for q in self.players if q is not lunatic], COUNTS[len(self.players)][2]
                    )
                    self.info(lunatic, {"minions": fake, "bluffs": self.bluffs})
            if lunatic:
                self.info(demon, {"lunatic": lunatic.id})
        script = SCRIPTS[self.config.script]
        for role in script.first_night if self.day == 1 else script.other_nights:
            for p in self.players:
                if p.role == role and (p.alive or role == "moonchild"):
                    yield from self._night_role(p)
                    self.check_victory()
                    if self.result:
                        return
        self.moon_targets.clear()
        self.gossips.clear()
        self.check_victory()
        if self.result:
            return
        self._dawn_state()
        self.emit("grimoire", self.grimoire(), [])
        self.phase = "day"
        self.died_today = self.outsider_died_today = False
        for pid in self.night_dead:
            self.by_id[pid].public_alive = False
        for pid in self.resurrected:
            self.by_id[pid].public_alive = self.socially_alive(self.by_id[pid])
        self.emit("phase", {"phase": "day", "day": self.day})
        self.emit("dawn", {"deaths": self.night_dead, "resurrected": self.resurrected})

    def _extra_day_options(self, p: Player) -> list[dict]:
        if not self.socially_alive(p) or f"gossip-{self.day}" in p.used:
            return []
        return [{"type": "gossip", "role": r} for r in SCRIPTS[self.config.script].roles] + [
            {"type": "gossip", "target": q.id, "alignment": alignment}
            for q in self.players
            for alignment in ("good", "evil")
        ]

    def _extra_day_action(self, p: Player, action: dict):
        if action["type"] != "gossip":
            return
        p.used.add(f"gossip-{self.day}")
        if "role" in action:
            statement = f"The {ROLES[action['role']].name} is in play."
            truth = any(q.role == action["role"] for q in self.players)
        else:
            q = self.by_id[action["target"]]
            statement = f"{q.name} is {action['alignment']}."
            truth = q.alignment == action["alignment"]
        self.emit("gossip", {"player": p.id, "text": statement})
        if p.role == "gossip":
            self.gossips[p.id] = truth

    def _moonchoices(self) -> Generator[Decision, dict, None]:
        for pid in list(self.moon_pending):
            p = self.by_id[pid]
            if p.public_alive:
                continue
            options = self._alive_targets()
            if options and not self.result:
                action = yield Decision(pid, "day_ability", ROLES["moonchild"].ability, options)
                target = self.by_id[action["target"]]
                p.used.add("moonchild")
                self.moon_targets.append((pid, target.id, target.alignment == "good"))
                self.emit("moonchild", {"player": pid, "target": target.id})
            self.moon_pending.discard(pid)

    def _day(self) -> Generator[Decision, dict, None]:
        yield from self._moonchoices()
        yield from super()._day()
        if self.mastermind_day == self.day and not self.result:
            self.finish("good", "Mastermind: no player was executed on the extra day")
        yield from self._moonchoices()
