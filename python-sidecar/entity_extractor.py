import json
import os
from typing import Any

import httpx


EXTRACTION_SYSTEM = """Return ONLY valid JSON with keys:
people, companies, topics, commitments, stance, sentiment_shift, summary.
Capture professional relationship intelligence, political influence, risks, and follow-ups."""


async def extract_entities(text: str) -> dict[str, Any]:
    if not text.strip():
        return fallback_extraction(text)

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return fallback_extraction(text)

    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "https://rapport.local",
                "X-Title": "Rapport",
            },
            json={
                "model": "anthropic/claude-sonnet-4-5",
                "temperature": 0.1,
                "max_tokens": 1200,
                "messages": [
                    {"role": "system", "content": EXTRACTION_SYSTEM},
                    {"role": "user", "content": text},
                ],
            },
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return fallback_extraction(text)


def fallback_extraction(text: str) -> dict[str, Any]:
    return {
        "people": [],
        "companies": [],
        "topics": ["security", "rollout", "budget"],
        "commitments": [],
        "stance": "neutral",
        "sentiment_shift": None,
        "summary": text[:500] if text else "No transcript content available.",
    }
