"""One strict, JSON-serializable configuration schema for browser and CLI."""

from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .roles import COUNTS, ROLES, SCRIPTS


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True, allow_inf_nan=False)


class ModelConfig(StrictModel):
    provider: Literal["mock", "codex", "openai", "anthropic", "einfra", "compatible"] = "mock"
    model: str = Field(default="demo", min_length=1, max_length=200)
    service_tier: Literal["default", "fast", "ultrafast"] = "default"
    base_url: str | None = None
    credential_env: str | None = Field(default=None, pattern=r"^[A-Z][A-Z0-9_]*$")
    generation: dict[str, float | int | str | list[str]] = Field(default_factory=dict)
    max_output_tokens: int = Field(default=512, ge=64, le=65536)
    context_tokens: int = Field(default=16000, ge=2048, le=2000000)
    memory: Literal["recent", "full", "notes"] = "recent"
    timeout_seconds: float = Field(default=60, ge=1, le=300)
    retries: int = Field(default=2, ge=0, le=5)
    input_cost_per_million: float | None = Field(default=None, ge=0)
    output_cost_per_million: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def capabilities(self):
        if self.service_tier != "default" and self.provider != "codex":
            raise ValueError("Service tiers are currently supported only by the Codex provider")
        if self.service_tier == "ultrafast" and self.model != "gpt-6-astra":
            raise ValueError("Ultrafast requires gpt-6-astra")
        if self.base_url:
            u = urlsplit(self.base_url)
            if u.username or u.password or u.query or u.fragment or not u.hostname:
                raise ValueError("Endpoint must not contain credentials, query parameters, or fragments")
            if u.scheme != "https" and not (
                u.scheme == "http" and u.hostname in ("localhost", "127.0.0.1", "::1")
            ):
                raise ValueError("Use HTTPS endpoints (HTTP is allowed only for loopback)")
        if self.provider == "compatible" and not self.base_url:
            raise ValueError("OpenAI-compatible providers require base_url")
        allowed = {"temperature", "top_p", "stop"}
        if self.provider in ("openai", "compatible", "einfra"):
            allowed |= {"seed", "frequency_penalty", "presence_penalty"}
        if self.provider == "anthropic":
            allowed |= {"top_k"}
        if self.provider == "openai" and self.model.startswith(("o1", "o3", "o4", "gpt-5")):
            allowed = {"reasoning_effort"}
        if self.provider == "codex":
            allowed = {"reasoning_effort"}
            if self.base_url or self.credential_env:
                raise ValueError("Codex uses the local CLI login, not an endpoint or credential variable")
        unknown = set(self.generation) - allowed
        if unknown:
            raise ValueError(
                f"Unsupported generation settings for {self.provider}/{self.model}: {sorted(unknown)}"
            )
        for key, value in self.generation.items():
            if key == "stop":
                if (
                    not isinstance(value, list)
                    or not 1 <= len(value) <= 4
                    or not all(isinstance(v, str) and v for v in value)
                ):
                    raise ValueError("stop must contain 1–4 nonempty strings")
            elif key == "reasoning_effort":
                if value not in ("low", "medium", "high"):
                    raise ValueError("reasoning_effort must be low, medium, or high")
            elif not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ValueError(f"{key} must be numeric")
            elif key == "temperature" and not 0 <= value <= (1 if self.provider == "anthropic" else 2):
                raise ValueError("temperature is outside provider range")
            elif key == "top_p" and not 0 <= value <= 1:
                raise ValueError("top_p must be between 0 and 1")
            elif key in ("frequency_penalty", "presence_penalty") and not -2 <= value <= 2:
                raise ValueError(f"{key} must be between -2 and 2")
            elif key == "top_k" and value < 0:
                raise ValueError("top_k must be nonnegative")
            elif key in ("top_k", "seed") and not isinstance(value, int):
                raise ValueError(f"{key} must be an integer")
        if self.max_output_tokens >= self.context_tokens:
            raise ValueError("context_tokens must exceed max_output_tokens")
        return self


class PlayerConfig(StrictModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,40}$")
    name: str = Field(min_length=1, max_length=60)
    persona: str = "builtin:analyst"
    model: dict = Field(default_factory=dict)


class Policy(StrictModel):
    misinformation: Literal["random", "truthful_when_possible"] = "random"
    registration: Literal["natural", "misregister", "random"] = "natural"
    mayor_bounce: Literal["never", "always", "random"] = "random"
    godfather_outsiders: Literal[-1, 1] = 1
    pacifist_save: Literal["never", "random", "always"] = "random"
    shabaloth_regurgitate: Literal["never", "random", "always"] = "random"
    tinker_death: Literal["never", "random"] = "never"
    imp_successor: Literal["first_seat", "random"] = "random"


class Limits(StrictModel):
    max_days: int = Field(default=20, ge=1, le=100)
    max_turns: int = Field(default=3000, ge=1, le=50000)
    max_tokens: int = Field(default=1000000, ge=1, le=100000000)
    runtime_seconds: float = Field(default=3600, ge=1, le=86400)
    action_retries: int = Field(default=2, ge=0, le=5)


class Conversations(StrictModel):
    rounds: int = Field(default=2, ge=0, le=20)
    whispers: bool = True
    max_message_chars: int = Field(default=1500, ge=100, le=10000)


class GameConfig(StrictModel):
    version: Literal[1] = 1
    name: str = Field(default="Trouble in Ravenswood", min_length=1, max_length=100)
    script: Literal["trouble_brewing", "bad_moon_rising"] = "trouble_brewing"
    seed: int = 42
    players: list[PlayerConfig] = Field(min_length=5, max_length=15)
    defaults: ModelConfig = Field(default_factory=ModelConfig)
    policy: Policy = Field(default_factory=Policy)
    limits: Limits = Field(default_factory=Limits)
    conversations: Conversations = Field(default_factory=Conversations)
    roles: list[str] | None = None
    shuffle_roles: bool = True

    def model_for(self, player: PlayerConfig) -> ModelConfig:
        base = self.defaults.model_dump()
        overrides = dict(player.model)
        if "generation" in overrides:
            generation = overrides.pop("generation")
            if not isinstance(generation, dict):
                raise ValueError("Player generation overrides must be an object")
            for key, value in generation.items():
                if value is None:
                    base["generation"].pop(key, None)
                else:
                    base["generation"][key] = value
        return ModelConfig.model_validate({**base, **overrides})

    @model_validator(mode="after")
    def valid_game(self):
        if any(p.id in ("public", "omniscient") for p in self.players):
            raise ValueError("Player IDs public and omniscient are reserved for inspection views")
        if len({p.id for p in self.players}) != len(self.players):
            raise ValueError("Player IDs must be unique")
        if len({p.name for p in self.players}) != len(self.players):
            raise ValueError("Player names must be unique")
        for p in self.players:
            self.model_for(p)
        if (
            self.script == "bad_moon_rising"
            and self.policy.godfather_outsiders == -1
            and COUNTS[len(self.players)][1] == 0
            and (self.roles is None or "godfather" in self.roles)
        ):
            raise ValueError("Godfather cannot remove an Outsider from a zero-Outsider setup")
        if self.roles is not None:
            if len(self.roles) != len(self.players) or len(set(self.roles)) != len(self.roles):
                raise ValueError("Choose one unique character for each seat")
            if any(r not in SCRIPTS[self.script].roles for r in self.roles):
                raise ValueError("Character does not belong to the selected script")
            counts = list(COUNTS[len(self.players)])
            if "baron" in self.roles:
                counts[0] -= 2
                counts[1] += 2
            if "godfather" in self.roles:
                delta = self.policy.godfather_outsiders
                counts[0] -= delta
                counts[1] += delta
            actual = [
                sum(ROLES[r].team == t for r in self.roles)
                for t in ("townsfolk", "outsider", "minion", "demon")
            ]
            if actual != counts:
                raise ValueError(
                    f"Setup requires Townsfolk/Outsider/Minion/Demon counts {counts}; got {actual}"
                )
        return self


def demo_config(count: int = 7) -> GameConfig:
    templates = [
        "analyst",
        "skeptic",
        "diplomat",
        "interrogator",
        "observer",
        "gambler",
        "contrarian",
        "performer",
        "strategist",
        "improviser",
    ]
    return GameConfig(
        players=[
            PlayerConfig(id=f"p{i + 1}", name=f"Player {i + 1}", persona=f"builtin:{templates[i % 10]}")
            for i in range(count)
        ]
    )
