import json
from typing import Any

from openrouter_client import chat, extract_content, parse_model_list

EXTRACTION_SYSTEM = """Return ONLY valid JSON with keys:
people, companies, topics, commitments, relations, unresolved, stance, sentiment_shift, summary.

people: list of names mentioned.
companies: list of company names mentioned.
topics: list of specific topics discussed (extract from content only, do not invent).
commitments: list of {owner, what, status (open|closed), due, source_quote}.
relations: list of {from, to, type, evidence, confidence} where type is one of:
  approves, blocks, escalates_to, influences, committed_to, awaits_from, endorsed_by.
unresolved: list of {holder, awaiting_from, what, since}.
stance: overall stance of the primary contact (champion|skeptic|neutral|blocker).
sentiment_shift: description of any stance change observed, or null.
summary: 1-2 sentence factual summary of the interaction.

Capture professional relationship intelligence, political influence, risks, and follow-ups.
Only extract what is explicitly present in the text. Return empty lists when nothing is found."""

_EXTRACTION_MODELS = parse_model_list("EXTRACTION_MODEL", "openrouter/owl-alpha,poolside/laguna-m.1:free")

_EMPTY_EXTRACTION: dict[str, Any] = {
    "people": [],
    "companies": [],
    "topics": [],
    "commitments": [],
    "relations": [],
    "unresolved": [],
    "stance": "neutral",
    "sentiment_shift": None,
    "summary": "",
}


async def extract_entities(text: str) -> dict[str, Any]:
    if not text.strip():
        return dict(_EMPTY_EXTRACTION)

    try:
        response = await chat(
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM},
                {"role": "user", "content": text},
            ],
            models=_EXTRACTION_MODELS,
            temperature=0.1,
            max_tokens=1200,
        )
        return json.loads(extract_content(response))
    except Exception:
        return dict(_EMPTY_EXTRACTION)


def has_meaningful_extraction(extracted: dict[str, Any]) -> bool:
    return bool(
        extracted.get("topics")
        or extracted.get("relations")
        or extracted.get("commitments")
        or extracted.get("unresolved")
        or extracted.get("summary")
    )
