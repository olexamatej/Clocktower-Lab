import json

import httpx
import pytest

from clocktower.config import ModelConfig, demo_config
from clocktower.providers import HTTPProvider, MockProvider
from clocktower.runner import Runner
from clocktower.storage import Store, project_run


@pytest.mark.parametrize("count", [5, 7, 10, 15])
async def test_offline_complete_games(tmp_path, count):
    config = demo_config(count)
    runner = Runner(config, Store(tmp_path))
    run = await runner.run()
    assert run["result"]["status"] == "completed"
    assert run["result"]["winner"] in ("good", "evil")
    assert len({p["persona"] for p in run["config"]["players"]}) == count
    assert all((tmp_path / "personas" / p["persona"]).exists() for p in run["config"]["players"])
    public = project_run(run, "public")
    assert "config" not in public and "personas" not in public
    assert not any(e["kind"] in ("role", "grimoire", "information") for e in public["events"])


async def test_mixed_provider_wire_protocol_and_isolation(tmp_path, monkeypatch):
    captured = []
    mock = MockProvider(12)

    async def handler(request):
        payload = json.loads(request.content)
        is_anthropic = request.url.path.endswith("/messages")
        prompt = json.loads(payload["messages"][-1]["content"])
        system = payload["system"] if is_anthropic else payload["messages"][0]["content"]
        assert "secret-test-value" not in json.dumps(payload)
        assert "config" not in prompt and "personas" not in prompt
        me = prompt["observation"]["self"]["id"]
        assert not any(
            e["kind"] == "role" and e["data"]["player"] != me for e in prompt["observation"]["events"]
        )
        captured.append((request.url.host, is_anthropic, me))
        completion = await mock.complete(ModelConfig(), system, prompt)
        if is_anthropic:
            assert request.headers["x-api-key"] == "secret-test-value"
            return httpx.Response(
                200,
                json={
                    "content": [{"type": "text", "text": completion.text}],
                    "usage": {"input_tokens": 1, "output_tokens": 1},
                },
            )
        assert request.headers["Authorization"] == "Bearer secret-test-value"
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": completion.text}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    for env in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "E_INFRA_API_TOKEN", "COMPATIBLE_API_KEY"):
        monkeypatch.setenv(env, "secret-test-value")
    config = demo_config()
    providers = ["openai", "einfra", "anthropic", "compatible"]
    for i, p in enumerate(config.players):
        p.model = {"provider": providers[i % 4], "model": "test-model"}
        if p.model["provider"] == "compatible":
            p.model["base_url"] = "https://models.example.test/v1"
    wire = HTTPProvider(httpx.MockTransport(handler))
    runner = Runner(config, Store(tmp_path), {p: wire for p in providers})
    run = await runner.run()
    assert run["result"]["status"] == "completed"
    assert {host for host, _, _ in captured} == {
        "api.openai.com",
        "api.anthropic.com",
        "llm.ai.e-infra.cz",
        "models.example.test",
    }
    assert "secret-test-value" not in json.dumps(run)


async def test_turn_limit_is_interruption_not_victory(tmp_path):
    config = demo_config()
    config.limits.max_turns = 1
    run = await Runner(config, Store(tmp_path)).run()
    assert run["result"]["status"] == "interrupted" and run["result"]["winner"] is None


def test_config_rejects_secrets_and_unsupported_parameters():
    with pytest.raises(ValueError):
        ModelConfig(provider="anthropic", generation={"seed": 4})
    with pytest.raises(ValueError):
        ModelConfig(base_url="https://secret@example.com/v1")
    with pytest.raises(ValueError):
        ModelConfig.model_validate({"api_key": "secret"})


def test_independent_generation_override_can_remove_shared_setting():
    config = demo_config()
    config.defaults.generation = {"temperature": 0.5, "top_p": 0.9}
    config.players[0].model = {
        "provider": "openai",
        "model": "o3",
        "generation": {"temperature": None, "top_p": None, "reasoning_effort": "low"},
    }
    assert config.model_for(config.players[0]).generation == {"reasoning_effort": "low"}
    assert config.model_for(config.players[1]).generation == {"temperature": 0.5, "top_p": 0.9}
