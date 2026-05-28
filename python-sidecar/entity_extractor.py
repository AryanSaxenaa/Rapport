import json
from typing import cast

from html_utils import strip_json_fences
from openrouter_client import chat, extract_content, parse_model_list
from sidecar_types import ExtractionResult

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

_EMPTY_EXTRACTION: ExtractionResult = {
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


class ExtractionError(Exception):
    def __init__(self, message: str, error_type: str = "extraction_failed"):
        super().__init__(message)
        self.error_type = error_type


async def extract_entities(text: str) -> ExtractionResult:
    if not text.strip():
        return {**_EMPTY_EXTRACTION}

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
        content = extract_content(response)
        if not content.strip():
            raise ExtractionError("Extraction model returned an empty response.", "empty_response")
        return cast(ExtractionResult, json.loads(strip_json_fences(content)))
    except ExtractionError:
        raise
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ExtractionError(
            f"Extraction model returned invalid data: {exc}",
            "malformed_response",
        ) from exc
    except Exception as exc:
        raise ExtractionError(
            f"Extraction API call failed: {exc}",
            "api_error",
        ) from exc


async def extract_entities_safe(text: str) -> tuple[ExtractionResult, str | None]:
    """Non-raising wrapper: returns (extraction, error_message_or_none)."""
    try:
        result = await extract_entities(text)
        return result, None
    except ExtractionError as exc:
        return {**_EMPTY_EXTRACTION}, str(exc)


def has_meaningful_extraction(extracted: ExtractionResult) -> bool:
    return bool(
        extracted.get("topics")
        or extracted.get("relations")
        or extracted.get("commitments")
        or extracted.get("unresolved")
        or extracted.get("summary")
    )
