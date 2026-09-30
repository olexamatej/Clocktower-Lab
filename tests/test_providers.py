import asyncio

import httpx
import pytest

from clocktower.config import ModelConfig, demo_config
from clocktower.providers import Completion, HTTPProvider, ProviderError
from clocktower.runner import Runner
from clocktower.storage import Store


async def test_rate_limit_retry_and_http_error_sanitization(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "secret-test")
    calls = []

    def transport(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(429, headers={"retry-after": "0"}, text="secret-test")
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "{}"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 2},
            },
        )

    result = await HTTPProvider(httpx.MockTransport(transport)).complete(
        ModelConfig(provider="openai", model="test"), "system", {}
    )
    assert result.input_tokens == 1 and len(calls) == 2
    bad = HTTPProvider(httpx.MockTransport(lambda req: httpx.Response(401, text="secret-test")))
    with pytest.raises(ProviderError) as error:
        await bad.complete(ModelConfig(provider="openai"), "system", {})
    assert "secret-test" not in str(error.value) and "401" in str(error.value)


async def test_invalid_actions_recover_with_legal_fallback(tmp_path):
    class Invalid:
        async def complete(self, *args):
            return Completion("not json", 1, 1)

    config = demo_config()
    config.limits.max_turns = 1
    config.limits.action_retries = 2
    run = await Runner(config, Store(tmp_path), {"mock": Invalid()}).run()
    assert sum(u["requests"] for u in run["usage"].values()) == 3
    assert len([e for e in run["events"] if e["kind"] == "fallback"]) == 1
    assert run["result"]["winner"] is None


async def test_stop_cancels_pending_provider(tmp_path):
    entered = asyncio.Event()
    cancelled = asyncio.Event()

    class Slow:
        async def complete(self, *args):
            entered.set()
            try:
                await asyncio.sleep(30)
            finally:
                cancelled.set()

    runner = Runner(demo_config(), Store(tmp_path), {"mock": Slow()})
    task = asyncio.create_task(runner.run())
    await asyncio.wait_for(entered.wait(), 2)
    runner.stop.set()
    run = await asyncio.wait_for(task, 2)
    assert cancelled.is_set()
    assert run["result"]["status"] == "interrupted" and run["result"]["winner"] is None


async def test_malformed_http_response_and_missing_content(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret-test")
    for response in (httpx.Response(200, text="not-json"), httpx.Response(200, json={})):
        provider = HTTPProvider(httpx.MockTransport(lambda req, response=response: response))
        with pytest.raises(ProviderError):
            await provider.complete(ModelConfig(provider="anthropic"), "system", {})


def test_malformed_code_fence_is_recoverable_validation_error():
    from clocktower.providers import parse_action

    with pytest.raises(ValueError):
        parse_action("``````")
