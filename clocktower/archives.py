"""Portable, versioned replay archives. Import never resumes a process or runs a model."""

import copy
import json
import math
import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .config import GameConfig, ModelConfig
from .personas import validate_persona

MAX_ARCHIVE_BYTES = 50 * 1024 * 1024


def validate_json(value, depth=0):
    """Bound arbitrary future event payloads without interpreting them as instructions."""
    if depth > 30:
        raise ValueError("Archive data is nested too deeply")
    if isinstance(value, dict):
        if len(value) > 10000 or any(not isinstance(k, str) for k in value):
            raise ValueError("Invalid archive object")
        for item in value.values():
            validate_json(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            validate_json(item, depth + 1)
    elif isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Archive numbers must be finite")
    elif value is not None and not isinstance(value, (str, bool, int, float)):
        raise ValueError("Archive must contain only JSON values")


def validate_event(event, ids):
    d = event.data

    def require(key, kind):
        if type(d.get(key)) is not kind:
            raise ValueError(f"Invalid {event.kind} event field {key}")

    def reference(value):
        if not isinstance(value, str) or value not in ids:
            raise ValueError("Event references an unknown player")

    for key in ("player", "nominator", "nominee", "target", "block"):
        if key in d and d[key] is not None:
            reference(d[key])
    if event.kind in (
        "role",
        "transformation",
        "death",
        "execution",
        "resurrection",
        "alignment",
        "information",
        "message",
        "slayer",
    ):
        reference(d.get("player"))
    if event.kind in ("role", "transformation"):
        require("role", str)
    if event.kind in ("role", "alignment") and d.get("alignment") not in ("good", "evil"):
        raise ValueError("Invalid alignment")
    if event.kind == "information":
        require("ability", str)
    if event.kind == "message":
        require("text", str)
    if event.kind == "gossip":
        reference(d.get("player"))
        require("text", str)
    if event.kind == "moonchild":
        reference(d.get("player"))
        reference(d.get("target"))
    if event.kind == "phase":
        if d.get("phase") not in ("setup", "night", "day"):
            raise ValueError("Invalid phase")
        require("day", int)
    if event.kind == "nomination":
        reference(d.get("nominator"))
        reference(d.get("nominee"))
    if event.kind == "vote":
        require("votes", dict)
        for player, vote in d["votes"].items():
            reference(player)
            if type(vote) is not bool:
                raise ValueError("Invalid vote value")
        reference(d.get("nominee"))
        require("tally", int)
        require("threshold", int)
    if event.kind == "dawn":
        require("deaths", list)
        for player in d["deaths"]:
            reference(player)
        if "resurrected" in d:
            require("resurrected", list)
            for player in d["resurrected"]:
                reference(player)
    if event.kind in ("setup", "grimoire"):
        require("players", list)
        seen = set()
        for player in d["players"]:
            if not isinstance(player, dict):
                raise ValueError("Invalid player snapshot")  # noqa: TRY004 - archive validation
            reference(player.get("id"))
            if player["id"] in seen:
                raise ValueError("Duplicate player snapshot")
            seen.add(player["id"])
            for key in ("role", "shown_role", "name", "alignment", "model", "provider"):
                if key in player and not isinstance(player[key], str):
                    raise ValueError("Invalid player snapshot text")
            for key in ("alive", "dead_vote", "poisoned"):
                if key in player and type(player[key]) is not bool:
                    raise ValueError("Invalid player snapshot state")
            if event.kind == "grimoire" and not {"role", "alive"} <= player.keys():
                raise ValueError("Incomplete grimoire snapshot")
        if seen != ids:
            raise ValueError("Incomplete player snapshot")
    if event.kind == "result":
        Result.model_validate(d)


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    seq: int = Field(ge=1)
    day: int = Field(ge=0)
    phase: Literal["setup", "night", "day"]
    kind: str = Field(min_length=1, max_length=80)
    data: dict
    audience: list[str] | None


class Result(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    status: Literal["completed", "interrupted"]
    winner: Literal["good", "evil"] | None
    reason: str = Field(max_length=4000)

    @model_validator(mode="after")
    def winner_matches_status(self):
        if (self.status == "completed") != (self.winner is not None):
            raise ValueError("Completed results need a winner; interruptions cannot award victory")
        return self


class UsageRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    requests: int = Field(ge=0)
    estimated: bool
    cost: float | None = Field(default=None, ge=0)


class RunRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")
    version: Literal[1]
    id: str = Field(min_length=1, max_length=80)
    created: datetime
    status: Literal["running", "completed", "interrupted"]
    config: GameConfig
    personas: dict[str, str]
    models: dict[str, ModelConfig]
    events: list[Event] = Field(max_length=500000)
    result: Result | None
    usage: dict[str, UsageRecord]
    turns: int = Field(ge=0)

    @model_validator(mode="after")
    def consistent(self):
        ids = {p.id for p in self.config.players}
        if set(self.personas) != ids or set(self.models) != ids or set(self.usage) != ids:
            raise ValueError("Archive must contain persona, model, and usage snapshots for every player")
        for text in self.personas.values():
            validate_persona(text)
        for index, event in enumerate(self.events, 1):
            if event.seq != index or (event.audience is not None and not set(event.audience) <= ids):
                raise ValueError("Invalid event sequence or audience")
            validate_event(event, ids)
        if self.status == "running":
            if self.result is not None:
                raise ValueError("Running snapshot cannot have a result")
        elif self.result is None or self.result.status != self.status:
            raise ValueError("Run status and result disagree")
        return self


class RunArchive(BaseModel):
    model_config = ConfigDict(extra="forbid")
    format: Literal["clocktower-run"]
    archive_version: Literal[1]
    run: RunRecord


def export_archive(record: dict) -> dict:
    # Do not serialize process IDs or filesystem handles. Keep original event audiences.
    run = RunRecord.model_validate(record).model_dump(mode="json")
    return {"format": "clocktower-run", "archive_version": 1, "run": run}


def import_archive(data: dict) -> dict:
    validate_json(data)
    if len(json.dumps(data, ensure_ascii=False).encode()) > MAX_ARCHIVE_BYTES:
        raise ValueError("Archive exceeds 50 MiB")
    archive = RunArchive.model_validate(data)
    record = archive.run.model_dump(mode="json")
    record["imported_from"] = record["id"]
    record["imported_at"] = datetime.now(UTC).isoformat()
    record["id"] = uuid.uuid4().hex
    if record["status"] == "running":
        record["status"] = "interrupted"
        record["result"] = {
            "status": "interrupted",
            "winner": None,
            "reason": "Imported snapshot of an in-progress game; replay only",
        }
        last = record["events"][-1] if record["events"] else {"day": 0, "phase": "setup"}
        record["events"].append(
            {
                "seq": len(record["events"]) + 1,
                "day": last["day"],
                "phase": last["phase"],
                "kind": "result",
                "data": copy.deepcopy(record["result"]),
                "audience": None,
            }
        )
    return record
