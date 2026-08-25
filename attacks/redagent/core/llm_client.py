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
from datetime import datetime, timezone
from typing import Any

import httpx


class LLMError(RuntimeError):
    pass


def _strip_code_fences(text: str) -> str:
    """Models frequently wrap JSON in ```json ...``` fences even when
    response_format=json_object is honored upstream (audit 06 open item).
    Strip the fence pair before parsing; return original if no fence found."""
    s = text.strip()
    if not s.startswith("```"):
        return s
    first_nl = s.find("\n")
    if first_nl != -1:
        s = s[first_nl + 1:]
    if s.rstrip().endswith("```"):
        s = s.rstrip()[:-3]
    return s.strip()


def _parse_retry_after(value: str | None, fallback: float) -> float:
    """Honor Retry-After whether it's seconds ('2', '0.5') or an HTTP-date.
    Non-429 paths previously ignored float values entirely ('0.5'.isdigit()
    is False), so servers asking for sub-second backoff were ignored."""
    if not value:
        return fallback
    v = value.strip()
    try:
        return max(0.0, float(v))
    except ValueError:
        pass
    try:
        from email.utils import parsedate_to_datetime
        delta = parsedate_to_datetime(v).timestamp() - datetime.now(timezone.utc).timestamp()
        return max(0.0, delta) if delta > 0 else fallback
    except Exception:
        return fallback


class _RateLimiter:
    """Shared min-interval throttle across all calls on one client.

    Free-tier models (OpenRouter ':free') enforce strict per-minute caps and
    often reject concurrent bursts. This serializes request STARTS by a
    configurable minimum interval; retries back off on top of it."""

    def __init__(self, min_interval_s: float):
        self._interval = max(0.0, min_interval_s)
        self._next_slot = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        if self._interval <= 0:
            return
        async with self._lock:
            now = asyncio.get_event_loop().time()
            wait = self._next_slot - now
            self._next_slot = max(now, self._next_slot) + self._interval
        if wait > 0:
            await asyncio.sleep(wait)



class LLMClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        models: dict[str, str],
        timeout_s: float = 120.0,
        max_retries: int = 5,
        min_interval_s: float = 0.0,
        reasoning_effort: str | None = None,
    ):
        if not base_url or not api_key:
            raise LLMError("LLM_BASE_URL and LLM_API_KEY must be set (see config/settings.example.env)")
        self._base = base_url.rstrip("/")
        self._key = api_key
        self._models = models
        self._timeout = timeout_s
        self._max_retries = max_retries
        self._limiter = _RateLimiter(min_interval_s)
        self._reasoning_effort = reasoning_effort  # e.g. "max" | "high" | "low"
        self.last_errors: list[str] = []  # per-call failure reasons from the last complete_many
        self._cx: httpx.AsyncClient | None = None   # shared connection pool (audit 06)

    def _client(self) -> httpx.AsyncClient:
        """Shared AsyncClient: one connection pool across all calls instead of
        a fresh TCP+TLS handshake per complete() — less latency, less socket
        churn under batch generation."""
        if self._cx is None or self._cx.is_closed:
            self._cx = httpx.AsyncClient(
                timeout=self._timeout,
                limits=httpx.Limits(max_connections=64, max_keepalive_connections=32),
            )
        return self._cx

    async def aclose(self) -> None:
        """Graceful shutdown of the shared pool (call on app shutdown)."""
        if self._cx is not None and not self._cx.is_closed:
            await self._cx.aclose()

    @classmethod
    def from_env(cls) -> "LLMClient":
        # Free-tier ':free' models get aggressive default throttling.
        default_interval = 3.0 if ":free" in os.environ.get("LLM_MODEL_STRATEGY", "") + os.environ.get("LLM_MODEL_BULK", "") else 0.0
        return cls(
            base_url=os.environ.get("LLM_BASE_URL", ""),
            api_key=os.environ.get("LLM_API_KEY", ""),
            models={
                "strategy": os.environ.get("LLM_MODEL_STRATEGY", ""),
                "bulk": os.environ.get("LLM_MODEL_BULK", ""),
            },
            min_interval_s=float(os.environ.get("LLM_MIN_INTERVAL_S", default_interval)),
            reasoning_effort=(os.environ.get("LLM_REASONING_EFFORT", "").strip() or None),
        )

    async def complete(
        self,
        tier: str,
        *,
        system: str | None = None,
        user: str = "",
        temperature: float = 0.8,
        json_mode: bool = False,
        reasoning_effort: str | None = None,
    ) -> str:
        """Attempt models in failover order. Model strings may be comma-separated
        chains, e.g. 'model-a:free, model-b:free' — on upstream 429 (saturated
        shared pool) the next model in the chain is tried.

        reasoning_effort: per-call override for the reasoning budget sent to
        reasoning models (OpenRouter unified 'reasoning' param). Falls back to
        LLM_REASONING_EFFORT from the environment."""
        chain = [m.strip() for m in (self._models.get(tier) or self._fallback_model()).split(",") if m.strip()]
        effort = reasoning_effort or self._reasoning_effort
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})

        last_err: Exception | None = None
        for model in chain:
            try:
                return await self._complete_with_model(model, messages, temperature, json_mode, effort)
            except LLMError as e:
                last_err = e
                if "429" not in str(e):
                    raise  # non-rate-limit errors are not fixed by another model
                print(f"[llm] {model} rate-limited upstream — failing over")
        raise LLMError(f"All models in chain failed: {last_err}")

    async def _complete_with_model(
        self, model: str, messages: list[dict[str, str]], temperature: float, json_mode: bool,
        reasoning_effort: str | None = None,
    ) -> str:
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        if reasoning_effort:
            # OpenRouter unified reasoning control; models that don't support it ignore it.
            body["reasoning"] = {"effort": reasoning_effort}

        delay = 1.0
        last_err: Exception | None = None
        consecutive_429 = 0
        cx = self._client()   # shared pool — no fresh TCP+TLS per call (audit 06)
        for attempt in range(self._max_retries):
            try:
                await self._limiter.acquire()
                r = await cx.post(
                    f"{self._base}/chat/completions",
                    headers={"Authorization": f"Bearer {self._key}"},
                    json=body,
                )
                r.raise_for_status()
                try:
                    data = r.json()
                except ValueError as e:  # HTML-200 / malformed body (audit 11/S6)
                    last_err = e
                    if attempt < self._max_retries - 1:
                        await asyncio.sleep(delay)
                        delay = min(delay * 2, 30)
                    continue
                usage = data.get("usage") or {}
                if usage:
                    print(f"[llm] {model} tokens in={usage.get('prompt_tokens')} "
                          f"out={usage.get('completion_tokens')}")
                return data["choices"][0]["message"]["content"]
            except (httpx.HTTPStatusError, httpx.TransportError, KeyError, IndexError) as e:
                last_err = e
                resp = getattr(e, "response", None)
                status_code = getattr(resp, "status_code", None)
                retryable = status_code is None or status_code in (429, 500, 502, 503, 529)
                if not retryable or attempt == self._max_retries - 1:
                    break
                retry_after = resp.headers.get("retry-after") if resp is not None else None
                if status_code == 429:
                    # 429 = quota/rate exhaustion. Retrying fast BURNS quota
                    # and makes things worse. Back off hard; give up after 2.
                    consecutive_429 += 1
                    if consecutive_429 > 2:
                        break
                    wait = _parse_retry_after(retry_after, 30.0)
                else:
                    wait = _parse_retry_after(retry_after, delay)
                    delay = min(delay * 2, 30)
                await asyncio.sleep(wait + random.uniform(0, 0.5))
        raise LLMError(f"LLM call failed after {self._max_retries} attempts: {last_err}")

    def _fallback_model(self) -> str:
        for m in self._models.values():
            if m:
                return m
        raise LLMError("No LLM models configured — set LLM_MODEL_STRATEGY / LLM_MODEL_BULK")

    async def complete_json(self, tier: str, **kw: Any) -> dict[str, Any]:
        kw["json_mode"] = True
        raw = await self.complete(tier, **kw)
        # try raw first (fast path), then fence-stripped (audit 06: models wrap
        # JSON in markdown fences despite json_mode — batch-killing parse class)
        last_err: json.JSONDecodeError | None = None
        for candidate in (raw, _strip_code_fences(raw)):
            try:
                return json.loads(candidate, strict=False)  # strict=False: tolerate raw control chars
            except json.JSONDecodeError as e:
                last_err = e
        raise LLMError(f"Model returned invalid JSON: {raw[:200]}...") from last_err

    async def complete_many(
        self, tier: str, prompts: list[str], *, max_concurrency: int = 32, **kw: Any
    ) -> list[str | None]:
        """Batch completion that never loses siblings on failure: failed prompts
        return None (bulk generation must survive partial outages)."""
        sem = asyncio.Semaphore(max_concurrency)
        self.last_errors = []

        async def one(p: str) -> str | None:
            async with sem:
                try:
                    return await self.complete(tier, user=p, **kw)
                except LLMError as e:
                    msg = str(e)
                    self.last_errors.append(msg)
                    print(f"[llm] prompt failed (isolated): {msg.splitlines()[0] if msg else 'unknown'}")
                    return None

        return list(await asyncio.gather(*(one(p) for p in prompts)))
