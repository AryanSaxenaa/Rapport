import asyncio
import os
from typing import Any

import httpx

RETRYABLE_STATUS_CODES = {429, 500, 503}
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_TIMEOUT = 45.0


def _get_api_key() -> str | None:
    return os.getenv("OPENROUTER_API_KEY")


def parse_model_list(env_var: str, default: str) -> list[str]:
    return [m.strip() for m in (os.getenv(env_var) or default).split(",") if m.strip()]


async def _with_retry[T](operation, max_retries: int = 3, base_delay: float = 2.0) -> T:
    for attempt in range(1, max_retries + 1):
        try:
            return await operation()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code not in RETRYABLE_STATUS_CODES or attempt == max_retries:
                raise
            await asyncio.sleep(base_delay ** attempt)
        except (httpx.ConnectError, httpx.TimeoutException):
            if attempt == max_retries:
                raise
            await asyncio.sleep(base_delay ** attempt)
    raise RuntimeError("OpenRouter retry loop exhausted")


async def chat(
    messages: list[dict[str, str]],
    models: list[str],
    temperature: float = 0.2,
    max_tokens: int = 1500,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    api_key = _get_api_key()
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not set")

    async def _call() -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "HTTP-Referer": "https://rapport.local",
                    "X-Title": "Rapport",
                },
                json={
                    "models": models,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "messages": messages,
                },
            )
            response.raise_for_status()
            return response.json()

    return await _with_retry(_call)


def extract_content(response: dict[str, Any]) -> str:
    return response["choices"][0]["message"]["content"]
