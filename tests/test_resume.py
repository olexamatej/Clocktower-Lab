"""Resumption reconstructs engine state without sending model requests."""

import copy
import json
from datetime import datetime

import pytest

from clocktower.config import ModelConfig, demo_config
from clocktower.providers import Completion
from clocktower.runner import Runner
from clocktower.storage import Store


class NotesProvider:
    def __init__(self):
        self.calls = 0

    async def complete(self, model, system, prompt):
        self.calls += 1
        action = dict(prompt["decision"]["options"][0])
        action["notes"] = f"Private memory for {prompt['observation']['self']['id']}"
        return Completion(json.dumps(action), 123, 17)


async def stopped_run(tmp_path, script):
    config = demo_config(10 if script == "sects_and_violets" else 7)
    config.script = script
    provider = NotesProvider()
    runner = Runner(config, Store(tmp_path), {"mock": provider})

    def stop_after_four(current):
        if current.turns == 4:
            current.stop.set()

    record = await runner.run(stop_after_four)
    assert record["status"] == "interrupted" and record["turns"] == 4
    return runner, json.loads(json.dumps(record)), provider


@pytest.mark.parametrize("script", ["trouble_brewing", "bad_moon_rising", "sects_and_violets"])
async def test_resume_retains_pending_memory_usage_identity_and_history(tmp_path, script):
    original, record, provider = await stopped_run(tmp_path, script)
    source = copy.deepcopy(record)
    resumed = Runner.resume(record, Store(tmp_path), max_tokens=0)
    assert record == source and provider.calls == 4
    assert resumed.id == original.id
    assert datetime.fromisoformat(resumed.created) == datetime.fromisoformat(original.created)
    assert resumed.notes == original.notes and resumed.usage == original.usage
    assert resumed.personas == original.personas and resumed.models == original.models
    assert resumed.engine.pending == original.engine.pending
    history = json.loads(json.dumps(resumed.engine.events))
    assert history == record["events"][:-1]
    assert resumed.turns == 4 and resumed.config.limits.max_tokens == 0
    resumed.providers["mock"] = provider
    resumed.config.limits.max_turns = 5
    result = await resumed.run()
    assert result["turns"] == 5 and provider.calls == 5
    assert json.loads(json.dumps(result["events"]))[: len(history)] == history
    assert sum(u["requests"] for u in result["usage"].values()) == 5


@pytest.mark.parametrize(
    "corruption", ["imported", "completed", "history", "turns", "missing_result", "wrong_result"]
)
async def test_resume_rejects_nonlocal_terminal_or_divergent_records(tmp_path, corruption):
    _, record, _ = await stopped_run(tmp_path, "trouble_brewing")
    if corruption == "imported":
        record["imported_from"] = "other-id"
    elif corruption == "completed":
        record["status"] = "completed"
        record["result"] = {"status": "completed", "winner": "good", "reason": "done"}
    elif corruption == "history":
        record["events"][0]["data"]["script"] = "bad_moon_rising"
    elif corruption == "turns":
        record["turns"] += 1
    elif corruption == "missing_result":
        record["events"].pop()
    elif corruption == "wrong_result":
        record["events"][-1]["data"]["reason"] = "Different interruption"
    with pytest.raises(ValueError):
        Runner.resume(record, Store(tmp_path))


@pytest.mark.parametrize("budget,expected_calls", [(0, 1), (1, 0)])
async def test_zero_token_budget_bypasses_reservation_and_post_response_limit(
    tmp_path, budget, expected_calls
):
    config = demo_config()
    config.defaults = ModelConfig(provider="codex", model="test")
    config.limits.max_tokens = budget
    config.limits.max_turns = 1
    provider = NotesProvider()
    runner = Runner(config, Store(tmp_path), {"codex": provider})
    result = await runner.run()
    assert provider.calls == expected_calls
    assert result["turns"] == expected_calls
    assert result["result"]["status"] == "interrupted"
