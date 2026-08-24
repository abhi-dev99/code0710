"""
Provider-agnostic LLM client for red-team agents.

Speaks the OpenAI-compatible chat-completions protocol against any
LLM_BASE_URL: OpenRouter, vendor APIs, or a local Ollama/vLLM server.

Tiered routing:
  - "strategy"  -> strong model, low volume (attack planning, mutation decisions)
  - "bulk"      -> cheap/fast model, high volume (persona/text generation)

Usage:
    client = LLMClient.from_env()
    plan = await client.complete_json("strategy", system=..., user=...)
    txts = await client.complete_many("bulk", prompts=[...], max_concurrency=32)
"""
from __future__ import annotations

import asyncio
import json
import os
import random
from typing import Any

import httpx


class LLMError(RuntimeError):
    pass


class LLMClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        models: dict[str, str],
        timeout_s: float = 120.0,
        max_retries: int = 5,
    ):
        if not base_url or not api_key:
            raise LLMError("LLM_BASE_URL and LLM_API_KEY must be set (see config/settings.example.env)")
        self._base = base_url.rstrip("/")
        self._key = api_key
        self._models = models
        self._timeout = timeout_s
        self._max_retries = max_retries

    @classmethod
    def from_env(cls) -> "LLMClient":
        return cls(
            base_url=os.environ.get("LLM_BASE_URL", ""),
            api_key=os.environ.get("LLM_API_KEY", ""),
            models={
                "strategy": os.environ.get("LLM_MODEL_STRATEGY", ""),
                "bulk": os.environ.get("LLM_MODEL_BULK", ""),
            },
        )

    async def complete(
        self,
        tier: str,
        *,
        system: str | None = None,
        user: str = "",
        temperature: float = 0.8,
        json_mode: bool = False,
    ) -> str:
        model = self._models.get(tier) or next(m for m in self._models.values() if m)
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})

        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}

        delay = 1.0
        last_err: Exception | None = None
        async with httpx.AsyncClient(timeout=self._timeout) as cx:
            for attempt in range(self._max_retries):
                try:
                    r = await cx.post(
                        f"{self._base}/chat/completions",
                        headers={"Authorization": f"Bearer {self._key}"},
                        json=body,
                    )
                    r.raise_for_status()
                    return r.json()["choices"][0]["message"]["content"]
                except (httpx.HTTPStatusError, httpx.TransportError, KeyError, IndexError) as e:
                    last_err = e
                    status = getattr(e, "response", None)
                    retryable = status is None or status.status_code in (429, 500, 502, 503, 529)
                    if not retryable or attempt == self._max_retries - 1:
                        break
                    await asyncio.sleep(delay + random.uniform(0, 0.5))
                    delay = min(delay * 2, 30)
        raise LLMError(f"LLM call failed after {self._max_retries} attempts: {last_err}")

    async def complete_json(self, tier: str, **kw: Any) -> dict[str, Any]:
        kw["json_mode"] = True
        raw = await self.complete(tier, **kw)
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise LLMError(f"Model returned invalid JSON: {raw[:200]}...") from e

    async def complete_many(
        self, tier: str, prompts: list[str], *, max_concurrency: int = 32, **kw: Any
    ) -> list[str]:
        sem = asyncio.Semaphore(max_concurrency)

        async def one(p: str) -> str:
            async with sem:
                return await self.complete(tier, user=p, **kw)

        return await asyncio.gather(*(one(p) for p in prompts))
