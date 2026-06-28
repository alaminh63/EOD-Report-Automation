"""
OpenRouter multi-model fallback router.

Uses httpx directly (no openai client) so we fully control retry behavior.
Tries models in priority order:
  1. OPENROUTER_MODEL from .env (if set)
  2. FREE_MODELS chain in order

Moves to next model on: 404, 429, 5xx, timeout, empty response.
Stops chain on: 401, 403 (bad key).
"""

import logging
import time
from dataclasses import dataclass, field

import httpx

from . import config

logger = logging.getLogger(__name__)

FREE_MODELS: list[str] = [
    "openai/gpt-oss-120b:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "nousresearch/hermes-3-llama-3.1-405b:free",
    "qwen/qwen3-next-80b-a3b-instruct:free",
    "qwen/qwen3-coder:free",
    "google/gemma-4-26b-a4b-it:free",
    "cohere/north-mini-code:free",
    "openai/gpt-oss-20b:free",
    "meta-llama/llama-3.2-3b-instruct:free",
    "liquid/lfm-2.5-1.2b-thinking:free",
]

_BASE = "https://openrouter.ai/api/v1/chat/completions"
_TIMEOUT = 12.0  # seconds per model


@dataclass
class ModelAttempt:
    model: str
    ok: bool
    error: str = ""
    latency_ms: int = 0


@dataclass
class RouterResult:
    text: str
    model_used: str
    attempts: list[ModelAttempt] = field(default_factory=list)


def _model_chain() -> list[str]:
    preferred = (config.OPENROUTER_MODEL or "").strip()
    seen: set[str] = set()
    chain: list[str] = []
    for m in ([preferred] if preferred else []) + FREE_MODELS:
        if m and m not in seen:
            seen.add(m)
            chain.append(m)
    return chain


def complete(
    prompt: str,
    max_tokens: int = 512,
    temperature: float = 0.3,
) -> RouterResult:
    if not config.OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY not set in .env — get key at openrouter.ai/keys")

    headers = {
        "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://cloudgen.bd",
        "X-Title": "CloudGen DDR",
    }

    chain = _model_chain()
    attempts: list[ModelAttempt] = []

    for model in chain:
        t0 = time.monotonic()
        logger.debug("Trying: %s", model)
        try:
            resp = httpx.post(
                _BASE,
                headers=headers,
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
                timeout=_TIMEOUT,
            )
            latency = int((time.monotonic() - t0) * 1000)

            if resp.status_code in (401, 403):
                err = f"HTTP {resp.status_code} — bad API key"
                attempts.append(ModelAttempt(model=model, ok=False, error=err, latency_ms=latency))
                logger.error("Auth error on %s — stopping chain", model)
                break

            if resp.status_code in (404, 429) or resp.status_code >= 500:
                err = f"HTTP {resp.status_code}"
                attempts.append(ModelAttempt(model=model, ok=False, error=err, latency_ms=latency))
                logger.warning("Skip [%s] %s", err, model)
                continue

            if resp.status_code != 200:
                err = f"HTTP {resp.status_code}"
                attempts.append(ModelAttempt(model=model, ok=False, error=err, latency_ms=latency))
                logger.warning("Unexpected status [%s] %s", err, model)
                continue

            data = resp.json()
            text = (data.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()

            if not text:
                attempts.append(ModelAttempt(model=model, ok=False, error="empty response", latency_ms=latency))
                logger.warning("Empty response: %s", model)
                continue

            logger.info("OK [%dms]: %s", latency, model)
            attempts.append(ModelAttempt(model=model, ok=True, latency_ms=latency))
            return RouterResult(text=text, model_used=model, attempts=attempts)

        except httpx.TimeoutException:
            latency = int((time.monotonic() - t0) * 1000)
            attempts.append(ModelAttempt(model=model, ok=False, error="timeout", latency_ms=latency))
            logger.warning("Timeout [%dms]: %s", latency, model)

        except Exception as e:
            latency = int((time.monotonic() - t0) * 1000)
            attempts.append(ModelAttempt(model=model, ok=False, error=str(e), latency_ms=latency))
            logger.warning("Error on %s: %s", model, e)

    lines = "\n".join(f"  • {a.model}: {a.error}" for a in attempts if not a.ok)
    raise RuntimeError(f"All {len(attempts)} model(s) failed:\n{lines}")


def get_model_chain() -> list[str]:
    return _model_chain()
