"""Sects & Violets' supported ten-player roster.

Other S&V characters are reference/bluff options only. Configuration rejects
unimplemented setups rather than silently giving those characters no ability.
"""

import itertools
from collections.abc import Generator

from .config import GameConfig
from .engine import Decision, Engine, Player
from .roles import ROLES, SCRIPTS, SV_RUN_ROLES


class SectsAndVioletsEngine(Engine):
    def __init__(self, config: GameConfig):
        self.curse: tuple[str, str] | None = None
        self.twins: tuple[str, str] | None = None
        self.executed_today = False
        super().__init__(config)

    def _draw_roles(self) -> list[str]:
        return list(SV_RUN_ROLES)

    def grimoire(self) -> dict:
        return {**super().grimoire(), "curse": self.curse, "twins": self.twins}

    def vortox_active(self) -> bool:
        p = self.role_player("vortox")
        return p is not None and self.functioning(p)

    def twin_source(self) -> Player | None:
        if self.twins:
            p = self.by_id[self.twins[0]]
            if p.role == "evil_twin" and self.functioning(p):
                return p
        return None

    def check_victory(self):
        demon_alive = any(p.alive and ROLES[p.role].team == "demon" for p in self.players)
        twins_alive = (
            self.twin_source() is not None and self.twins is not None and self.by_id[self.twins[1]].alive
        )
        if not demon_alive and not twins_alive:
            self.finish("good", "No living Demon or active twin pair remains")
        elif demon_alive and len(self.living()) <= 2:
            self.finish("evil", "Only two players remain alive")

    def _number(self, p: Player, value: int, maximum: int, minimum: int = 0):
        if self.vortox_active():
            value = self.choice("Vortox false number", [n for n in range(minimum, maximum + 1) if n != value])
        elif self.impaired(p) and self.config.policy.misinformation == "random":
            value = self.choice("impaired number", list(range(minimum, maximum + 1)))
        self.info(p, value)

    def _boolean(self, p: Player, value: bool, key: str, **details):
        if self.vortox_active():
            value = not value
        elif self.impaired(p) and self.config.policy.misinformation == "random":
            value = self.choice("impaired boolean", [False, True])
        self.info(p, {**details, key: value})

    def _sage(self, p: Player, killer: Player):
        pairs = list(itertools.combinations([q.id for q in self.players if q != p], 2))
        if self.vortox_active():
            pairs = [
                pair for pair in pairs if all(ROLES[self.by_id[pid].role].team != "demon" for pid in pair)
            ]
        elif not self.impaired(p) or self.config.policy.misinformation != "random":
            pairs = [pair for pair in pairs if killer.id in pair]
        self.info(p, {"demon_in": list(self.choice("Sage pair", pairs))})

    def _kill(self, target: Player, cause: str, source: Player | None = None):
        if not target.alive:
            return
        twin_loss = (
            cause == "execution"
            and self.twin_source() is not None
            and self.twins is not None
            and target.id == self.twins[1]
        )
        target.alive = False
        if self.phase == "night":
            self.night_dead.append(target.id)
            self.emit("death", {"player": target.id, "cause": cause}, [])
        else:
            target.public_alive = False
            self.emit("death", {"player": target.id, "cause": cause})
        if target.role == "sage" and cause == "demon" and source is not None:
            self._sage(target, source)
        if len(self.living()) <= 3:
            self.curse = None
        if twin_loss:
            self.finish("evil", "The good twin was executed while the Evil Twin had their ability")
        else:
            self.check_victory()

    def _execute(self, target: Player):
        self.executed_today = True
        if not target.alive and self.twin_source() is not None and self.twins and target.id == self.twins[1]:
            self.emit("execution", {"player": target.id})
            self.finish("evil", "The good twin was executed while the Evil Twin had their ability")
            return
        super()._execute(target)

    def _on_nomination(self, nominator: Player):
        if self.curse and nominator.id == self.curse[1] and len(self.living()) > 3:
            witch = self.by_id[self.curse[0]]
            if witch.role == "witch" and self.functioning(witch):
                self._kill(nominator, "witch", witch)

    def _night_role(self, p: Player) -> Generator[Decision, dict, None]:
        role = p.role
        if role == "evil_twin":
            other = self.by_id[
                self.choice("Good twin", [q.id for q in self.players if q.alignment != p.alignment])
            ]
            self.twins = (p.id, other.id)
            for player, counterpart in ((p, other), (other, p)):
                # This information comes from a Minion, not the good twin's
                # Townsfolk ability, so Vortox does not falsify it.
                self.emit(
                    "information",
                    {
                        "player": player.id,
                        "ability": "evil_twin",
                        "value": {"twin": counterpart.id, "role": counterpart.role},
                    },
                    [player.id],
                )
        elif role == "witch":
            if len(self.living()) <= 3:
                return
            action = yield Decision(p.id, "night", ROLES[role].ability, self._targets())
            if self.functioning(p):
                self.curse = (p.id, action["target"])
        elif role == "vortox":
            action = yield Decision(p.id, "night", ROLES[role].ability, self._targets())
            if self.functioning(p):
                self._kill(self.by_id[action["target"]], "demon", p)
        elif role == "clockmaker":
            demons = [i for i, q in enumerate(self.players) if ROLES[q.role].team == "demon"]
            minions = [i for i, q in enumerate(self.players) if ROLES[q.role].team == "minion"]
            size = len(self.players)
            distance = min(min(abs(d - m), size - abs(d - m)) for d in demons for m in minions)
            self._number(p, distance, size // 2, 1)
        elif role == "dreamer":
            action = yield Decision(p.id, "night", ROLES[role].ability, self._targets(p.id))
            target = self.by_id[action["target"]]
            pool = SCRIPTS[self.config.script].roles
            good = [r for r in pool if ROLES[r].team in ("townsfolk", "outsider")]
            evil = [r for r in pool if ROLES[r].team in ("minion", "demon")]
            false = self.vortox_active()
            impaired = self.impaired(p) and self.config.policy.misinformation == "random"
            pair = []
            for group in (good, evil):
                if target.role in group and not false and not impaired:
                    pair.append(target.role)
                else:
                    candidates = [r for r in group if r != target.role] if false else group
                    pair.append(self.choice("Dreamer character", candidates))
            self.info(p, {"target": target.id, "characters": pair})
        elif role == "flowergirl":
            demon_ids = [q.id for q in self.players if ROLES[q.role].team == "demon"]
            voted = any(
                e["kind"] == "vote"
                and e["day"] == self.day - 1
                and any(e["data"]["votes"].get(pid) for pid in demon_ids)
                for e in self.events
            )
            self._boolean(p, voted, "demon_voted")
        elif role == "town_crier":
            nominated = any(
                e["kind"] == "nomination"
                and e["day"] == self.day - 1
                and ROLES[self.by_id[e["data"]["nominator"]].role].team == "minion"
                for e in self.events
            )
            self._boolean(p, nominated, "minion_nominated")
        elif role == "oracle":
            self._number(
                p, sum(not q.alive and q.alignment == "evil" for q in self.players), len(self.players)
            )
        elif role == "seamstress" and role not in p.used:
            options = [{"type": "pass"}] + [
                {"type": "choose", "targets": list(pair)}
                for pair in itertools.combinations([q.id for q in self.players if q != p], 2)
            ]
            action = yield Decision(p.id, "night", ROLES[role].ability, options)
            if action["type"] != "pass":
                p.used.add(role)
                a, b = [self.by_id[pid] for pid in action["targets"]]
                self._boolean(p, a.alignment == b.alignment, "same_alignment", targets=action["targets"])

    def _night(self) -> Generator[Decision, dict, None]:
        self.phase = "night"
        self.day += 1
        self.night_dead = []
        self.curse = None
        self.emit("phase", {"phase": "night", "day": self.day})
        if self.day == 1:
            demon = next(p for p in self.players if ROLES[p.role].team == "demon")
            minions = [p.id for p in self.players if ROLES[p.role].team == "minion"]
            self.info(demon, {"minions": minions, "bluffs": self.bluffs})
            for pid in minions:
                self.info(self.by_id[pid], {"demon": demon.id, "minions": [m for m in minions if m != pid]})
        script = SCRIPTS[self.config.script]
        for role in script.first_night if self.day == 1 else script.other_nights:
            for p in self.players:
                if p.role == role and p.alive:
                    yield from self._night_role(p)
                    if self.result:
                        return
        self.emit("grimoire", self.grimoire(), [])
        self.phase = "day"
        self.emit("phase", {"phase": "day", "day": self.day})
        for pid in self.night_dead:
            self.by_id[pid].public_alive = False
        self.emit("dawn", {"deaths": self.night_dead})

    def _day(self) -> Generator[Decision, dict, None]:
        self.executed_today = False
        yield from super()._day()
        if not self.result and not self.executed_today and self.vortox_active():
            self.finish("evil", "Nobody was executed while the Vortox was alive and healthy")
