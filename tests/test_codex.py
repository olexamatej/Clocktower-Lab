"""Codex subprocess contract; never sends a live model request."""

import asyncio
import json
import signal
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from clocktower.config import ModelConfig
from clocktower.providers import CodexProvider, ProviderError


def prompt(text=True):
    return {
        "observation": {"self": {"id": "p1"}, "events": []},
        "decision": {"options": [{"type": "pass"}, {"type": "speak"}], "text": text},
        "memory": "my private notes",
    }


def install_process(monkeypatch, answer, stdout=None, returncode=0):
    calls = []
    if stdout is None:
        stdout = json.dumps(
            {"type": "turn.completed", "usage": {"input_tokens": 13, "output_tokens": 7}}
        ).encode()

    async def spawn(*args, **kwargs):
        root = Path(kwargs["cwd"])
        calls.append((args, kwargs, json.loads((root / "schema.json").read_text())))
        (root / "answer.json").write_text(json.dumps(answer))
        process = AsyncMock()
        process.returncode = returncode
        process.communicate.return_value = (stdout, None)
        calls[-1] += (process,)
        return process

    monkeypatch.setattr("clocktower.providers.asyncio.create_subprocess_exec", spawn)
    return calls


@pytest.mark.parametrize("text", [True, False])
async def test_structured_mapping_usage_and_isolated_tool_free_request(monkeypatch, text):
    calls = install_process(monkeypatch, {"option": 1, "text": "My claim", "notes": "Remember claim"})
    supplied = prompt(text)
    config = ModelConfig(provider="codex", model="test-model", generation={"reasoning_effort": "high"})
    for _ in range(2):
        completion = await CodexProvider().complete(config, "Player persona", supplied)
        action = json.loads(completion.text)
        assert action == {
            "type": "speak",
            "notes": "Remember claim",
            **({"text": "My claim"} if text else {}),
        }
        assert (completion.input_tokens, completion.output_tokens, completion.estimated) == (13, 7, False)
    assert calls[0][1]["cwd"] != calls[1][1]["cwd"]
    for args, kwargs, schema, process in calls:
        assert not Path(kwargs["cwd"]).exists()
        assert args[:2] == ("codex", "exec") and args[-1] == "-"
        assert "--ephemeral" in args and "--ignore-user-config" in args
        assert args[args.index("--sandbox") + 1] == "read-only"
        assert args[args.index("--cd") + 1] == kwargs["cwd"]
        assert kwargs["start_new_session"] is True
        assert kwargs["stderr"] == asyncio.subprocess.DEVNULL
        settings = dict(args[i + 1].split("=", 1) for i, arg in enumerate(args) if arg == "-c")
        assert settings["approval_policy"] == '"never"'
        assert settings["project_doc_max_bytes"] == "0"
        assert settings["web_search"] == '"disabled"'
        for feature in (
            "shell_tool",
            "unified_exec",
            "shell_snapshot",
            "multi_agent",
            "apps",
            "plugins",
            "hooks",
            "memories",
        ):
            assert settings[f"features.{feature}"] == "false"
        assert settings["tools.view_image"] == "false"
        assert settings["model_reasoning_effort"] == '"high"'
        assert schema["properties"]["option"]["enum"] == [0, 1]
        content = process.communicate.call_args.args[0].decode()
        assert content.startswith("Player persona")
        assert json.loads(content.splitlines()[-1]) == supplied
        assert "other-player-secret" not in content


@pytest.mark.parametrize(
    "answer,stdout,code",
    [
        ({"option": 0, "text": "", "notes": ""}, b"secret-token", 1),
        ({"option": 0, "text": "", "notes": ""}, b"secret-token", 0),
        ({"option": True, "text": "", "notes": ""}, None, 0),
        ({"option": 99, "text": "", "notes": ""}, None, 0),
        ({"option": 0}, None, 0),
        ({"option": 0, "text": [], "notes": ""}, None, 0),
        ({"option": 0, "text": "", "notes": {}}, None, 0),
        ([], None, 0),
        (
            {"option": 0, "text": "", "notes": ""},
            b'{"type":"turn.completed","usage":{"input_tokens":-1,"output_tokens":2}}',
            0,
        ),
    ],
)
async def test_failure_is_sanitized(monkeypatch, answer, stdout, code):
    calls = install_process(monkeypatch, answer, stdout, code)
    with pytest.raises(ProviderError) as error:
        await CodexProvider().complete(ModelConfig(provider="codex"), "persona", prompt())
    assert "secret-token" not in str(error.value)
    assert not Path(calls[0][1]["cwd"]).exists()


async def test_missing_cli_has_actionable_safe_error(monkeypatch):
    monkeypatch.setattr(
        "clocktower.providers.asyncio.create_subprocess_exec",
        AsyncMock(side_effect=FileNotFoundError("secret-token")),
    )
    with pytest.raises(ProviderError, match="install it and run codex login") as error:
        await CodexProvider().complete(ModelConfig(provider="codex"), "persona", prompt())
    assert "secret-token" not in str(error.value)


@pytest.mark.parametrize("cancel", [True, False])
async def test_cancellation_or_timeout_kills_process_group_and_removes_workdir(monkeypatch, cancel):
    entered = asyncio.Event()
    roots = []
    process = AsyncMock()
    process.returncode = None
    process.pid = 12345

    async def communicate(data):
        entered.set()
        await asyncio.Event().wait()

    process.communicate.side_effect = communicate

    async def spawn(*args, **kwargs):
        roots.append(Path(kwargs["cwd"]))
        return process

    killed = []
    monkeypatch.setattr("clocktower.providers.asyncio.create_subprocess_exec", spawn)
    monkeypatch.setattr("clocktower.providers.os.killpg", lambda pid, sig: killed.append((pid, sig)))
    task = asyncio.create_task(
        CodexProvider().complete(ModelConfig(provider="codex", timeout_seconds=1), "persona", prompt())
    )
    await asyncio.wait_for(entered.wait(), 2)
    if cancel:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    else:
        with pytest.raises(ProviderError, match="Codex request timed out"):
            await task
    assert killed == [(12345, signal.SIGKILL)]
    process.wait.assert_awaited_once()
    assert not roots[0].exists()


@pytest.mark.parametrize(
    "settings",
    [
        {"generation": {"temperature": 0.5}},
        {"generation": {"reasoning_effort": "ultra"}},
        {"base_url": "https://example.com"},
        {"credential_env": "CODEX_SECRET"},
    ],
)
def test_codex_rejects_unsupported_settings(settings):
    with pytest.raises(ValueError):
        ModelConfig(provider="codex", **settings)


async def test_astra_ultrafast_service_tier_subprocess_flag(monkeypatch):
    calls = install_process(monkeypatch, {"option": 0, "text": "", "notes": ""})
    config = ModelConfig(provider="codex", model="gpt-6-astra", service_tier="ultrafast")
    await CodexProvider().complete(config, "persona", prompt())
    args = calls[0][0]
    assert args[args.index("--model") + 1] == "gpt-6-astra"
    assert 'service_tier="ultrafast"' in args


@pytest.mark.parametrize(
    "settings",
    [
        {"provider": "openai", "model": "gpt-6-astra", "service_tier": "ultrafast"},
        {"provider": "codex", "model": "gpt-6.1-sol", "service_tier": "ultrafast"},
        {"provider": "codex", "model": "gpt-6-astra", "service_tier": "invalid"},
    ],
)
def test_rejects_invalid_service_tier(settings):
    with pytest.raises(ValueError):
        ModelConfig(**settings)
