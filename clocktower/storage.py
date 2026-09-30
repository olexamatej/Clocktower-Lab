"""Versioned atomic file persistence, shared by web and CLI."""

import json
import re
import uuid
from pathlib import Path
from typing import Any

from .config import GameConfig
from .personas import PersonaStore


def atomic_json(path: Path, data: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


class Store:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.personas = PersonaStore(self.root / "personas")
        for name in ("configs", "runs"):
            (self.root / name).mkdir(parents=True, exist_ok=True)

    def path(self, kind: str, key: str) -> Path:
        if kind not in ("configs", "runs") or not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", key):
            raise ValueError("Invalid storage identifier")
        return self.root / kind / (key + ".json")

    def read(self, kind: str, key: str) -> dict:
        return json.loads(self.path(kind, key).read_text(encoding="utf-8"))

    def write(self, kind: str, key: str, data: dict):
        atomic_json(self.path(kind, key), data)

    def list(self, kind: str) -> list[dict]:
        result = []
        for path in sorted((self.root / kind).glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            data = json.loads(path.read_text())
            result.append(
                {
                    "id": path.stem,
                    "name": data.get("name", data.get("config", {}).get("name", path.stem)),
                    "status": data.get("status"),
                    "result": data.get("result"),
                    "created": data.get("created"),
                }
            )
        return result

    def materialize(self, config: GameConfig, *, duplicate: bool = False) -> GameConfig:
        data = config.model_dump()
        seen: set[str] = set()
        for p in data["players"]:
            ref = p["persona"]
            self.personas.read(ref)
            if duplicate or ref.startswith("builtin:") or ref in seen:
                p["persona"] = self.personas.copy(ref)
            seen.add(p["persona"])
        return GameConfig.model_validate(data)

    def save_config(
        self, config: GameConfig, key: str | None = None, *, duplicate: bool = False
    ) -> tuple[str, GameConfig]:
        config = self.materialize(config, duplicate=duplicate)
        key = key or uuid.uuid4().hex
        self.write("configs", key, config.model_dump())
        return key, config


def project_run(run: dict, viewer: str) -> dict:
    """Never ship the omniscient run to a public/player browser view."""
    players = run["config"]["players"]
    ids = {p["id"] for p in players}
    if viewer not in ("public", "omniscient") and viewer not in ids:
        raise ValueError("Unknown viewer")
    events = [
        e for e in run["events"] if viewer == "omniscient" or e["audience"] is None or viewer in e["audience"]
    ]
    result = {k: run.get(k) for k in ("id", "created", "status", "result", "version")}
    result["name"] = run["config"]["name"]
    result["players"] = [
        {
            "id": p["id"],
            "name": p["name"],
            "model": run["models"][p["id"]]["model"],
            "provider": run["models"][p["id"]]["provider"],
        }
        for p in players
    ]
    result["events"] = [{**e, "seq": i + 1, "audience": None} for i, e in enumerate(events)]
    if viewer == "omniscient":
        result.update({k: run[k] for k in ("config", "personas", "usage", "models")})
    return result
