"""Backend-only provider adapters. No raw HTTP error bodies are propagated."""

from __future__ import annotations

import asyncio
import json
import os
import random
from dataclasses import dataclass
from typing import Protocol

import httpx

from .config import ModelConfig

ENDPOINTS = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "einfra": "https://llm.ai.e-infra.cz/v1",
}
CREDENTIALS = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "einfra": "E_INFRA_API_TOKEN",
    "compatible": "COMPATIBLE_API_KEY",
}


class ProviderError(Exception):
    pass


@dataclass
class Completion:
    text: str
    input_tokens: int
    output_tokens: int
    estimated: bool = False


class Provider(Protocol):
    async def complete(self, config: ModelConfig, system: str, prompt: dict) -> Completion: ...


def token_bound(text: str) -> int:
    """Conservative byte bound for unknown tokenizers (not a billing estimate)."""
    return len(text.encode("utf-8")) + 64


class HTTPProvider:
    def __init__(self, transport: httpx.AsyncBaseTransport | None = None):
        self.transport = transport

    def credentials(self, config: ModelConfig) -> tuple[str, dict]:
        name = config.credential_env or CREDENTIALS[config.provider]
        secret = os.getenv(name, "")
        if not secret and config.provider != "compatible":
            raise ProviderError(f"Missing backend environment variable {name}")
        headers = {"Content-Type": "application/json"}
        if config.provider == "anthropic":
            headers.update({"x-api-key": secret, "anthropic-version": "2023-06-01"})
        elif secret:
            headers["Authorization"] = f"Bearer {secret}"
        base = config.base_url or ENDPOINTS.get(config.provider, "")
        return base.rstrip("/"), headers

    async def request(self, config: ModelConfig, method: str, path: str, payload: dict | None = None) -> dict:
        base, headers = self.credentials(config)
        async with httpx.AsyncClient(
            transport=self.transport, timeout=config.timeout_seconds, follow_redirects=False
        ) as client:
            for attempt in range(config.retries + 1):
                delay = min(2**attempt, 8)
                try:
                    response = await client.request(method, base + path, headers=headers, json=payload)
                    if (
                        response.status_code == 429 or response.status_code >= 500
                    ) and attempt < config.retries:
                        retry = response.headers.get("retry-after", "")
                        if retry.isdigit():
                            delay = min(int(retry), 15)
                        await asyncio.sleep(delay)
                        continue
                    if response.status_code >= 300:
                        raise ProviderError(
                            f"{config.provider} HTTP {response.status_code}; check credentials, model, endpoint, and supported settings"
                        )
                    try:
                        data = response.json()
                        if not isinstance(data, dict):
                            raise ValueError()  # noqa: TRY004 - caught as malformed response
                        return data
                    except (ValueError, TypeError):
                        raise ProviderError(f"{config.provider} returned malformed JSON") from None
                except httpx.TransportError:
                    if attempt == config.retries:
                        raise ProviderError(
                            f"{config.provider} connection failed or timed out after {attempt + 1} attempts"
                        ) from None
                    await asyncio.sleep(delay)
        raise ProviderError("Provider request failed")

    async def models(self, config: ModelConfig) -> list[str]:
        data = await self.request(config, "GET", "/models")
        models = data.get("data")
        if not isinstance(models, list):
            raise ProviderError("Provider returned a malformed model list")
        return [m["id"] for m in models if isinstance(m, dict) and isinstance(m.get("id"), str)]

    async def complete(self, config: ModelConfig, system: str, prompt: dict) -> Completion:
        content = json.dumps(prompt, ensure_ascii=False)
        generation = dict(config.generation)
        if config.provider == "anthropic":
            if "stop" in generation:
                generation["stop_sequences"] = generation.pop("stop")
            payload = {
                "model": config.model,
                "system": system,
                "messages": [{"role": "user", "content": content}],
                "max_tokens": config.max_output_tokens,
                **generation,
            }
            data = await self.request(config, "POST", "/messages", payload)
            try:
                text = "\n".join(b["text"] for b in data["content"] if b.get("type") == "text")
                usage = data.get("usage", {})
                inp, out = usage.get("input_tokens"), usage.get("output_tokens")
            except (KeyError, TypeError, AttributeError):
                raise ProviderError("Anthropic response omitted message content") from None
        else:
            token_key = "max_completion_tokens" if config.provider == "openai" else "max_tokens"
            payload = {
                "model": config.model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": content}],
                token_key: config.max_output_tokens,
                **generation,
            }
            data = await self.request(config, "POST", "/chat/completions", payload)
            try:
                text = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                inp, out = usage.get("prompt_tokens"), usage.get("completion_tokens")
            except (KeyError, TypeError, IndexError, AttributeError):
                raise ProviderError("Chat completion omitted message content") from None
        if not isinstance(text, str) or not text.strip():
            raise ProviderError("Provider returned no text; increase output budget if reasoning consumed it")
        estimated = not isinstance(inp, int) or not isinstance(out, int)
        if any(isinstance(v, int) and (isinstance(v, bool) or v < 0) for v in (inp, out)):
            raise ProviderError("Provider returned invalid token usage")
        return Completion(
            text,
            inp if isinstance(inp, int) else token_bound(system + content),
            out if isinstance(out, int) else token_bound(text),
            estimated,
        )


class MockProvider:
    """An observation-only policy: no engine handle, no omniscient state."""

    def __init__(self, seed: int):
        self.rng = random.Random(seed)

    async def complete(self, config: ModelConfig, system: str, prompt: dict) -> Completion:
        decision = prompt["decision"]
        options = decision["options"]
        obs = prompt["observation"]
        me = obs["self"]
        alive = {p["id"] for p in obs["players"] if p["alive"]}
        useful = [a for a in options if a.get("target") in alive and a.get("target") != me["id"]]
        if decision["kind"] == "conversation":
            action = {
                "type": "speak",
                "text": f"I am comparing the claims from day {obs['day']}. Which result can someone corroborate?",
            }
        elif decision["kind"] == "vote":
            action = options[-1] if self.rng.random() < 0.8 else options[0]
        elif decision["kind"] == "nomination":
            action = self.rng.choice(useful) if useful and self.rng.random() < 0.7 else options[0]
        else:
            action = self.rng.choice(useful or options)
        return Completion(json.dumps(action), 0, 0)


def parse_action(text: str) -> dict:
    text = text.strip()
    if text.startswith("```") and text.endswith("```"):
        if "\n" not in text:
            raise ValueError("Fenced JSON must have an opening line and JSON content")
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    try:
        action = json.loads(text)
    except (ValueError, TypeError):
        raise ValueError("Respond with one JSON action, without prose") from None
    if not isinstance(action, dict):
        raise ValueError("Respond with a JSON object")  # noqa: TRY004 - action validation
    return action
