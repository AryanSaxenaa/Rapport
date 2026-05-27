import asyncio
import json
import re
from typing import Any

from hydradb_client import (
    TENANT_ID,
    API_KEY,
    _hydradb_client,
    _sub_tenant_id,
    _with_retry,
    _error_payload,
    _to_plain_data,
)
from openrouter_client import chat, extract_content, parse_model_list
from sidecar_types import OpenRouterResponse

_BRIEF_MODELS = parse_model_list("BRIEF_MODEL", "openrouter/owl-alpha,poolside/laguna-m.1:free")

# Matches leading ```json / ``` fences that LLMs add around JSON responses.
_FENCE_RE = re.compile(r"^```[a-z]*\n?", re.MULTILINE)


async def generate_pre_call_brief(contact_email: str, contact_name: str, company: str) -> dict[str, Any]:
    context = await _recall_contact_context(contact_email, contact_name, company)
    try:
        response = await chat(
            messages=[{
                "role": "user",
                "content": (
                    f"Create a pre-call brief as JSON for {contact_name} at {company}.\n"
                    f"Use this recalled context:\n{context}\n\n"
                    "Return keys: contactName, company, currentStance, stanceShiftNote, topConcerns, "
                    "communicationStyle, talkingPoints, landmines, lastInteraction, powerNote."
                ),
            }],
            models=_BRIEF_MODELS,
            temperature=0.2,
            max_tokens=1500,
        )
        return json.loads(_strip_json_fences(extract_content(response)))
    except Exception:
        return _fallback_brief(contact_name, company, context)


def _strip_json_fences(text: str) -> str:
    """Remove markdown code fences that LLMs commonly wrap JSON responses in."""
    text = _FENCE_RE.sub("", text.strip())
    return text.rstrip("`").strip()


async def _recall_contact_context(contact_email: str, contact_name: str, company: str) -> str:
    if not API_KEY:
        return "HydraDB key missing. Using local demo context."

    client = _hydradb_client()
    if not client:
        return "HydraDB client unavailable."

    try:
        prefs, knowledge = await asyncio.gather(
            _with_retry(
                lambda: client.recall.recall_preferences(
                    tenant_id=TENANT_ID,
                    sub_tenant_id=_sub_tenant_id(contact_email),
                    query=f"{contact_name} preferences stance concerns commitments",
                    max_results=12,
                    mode="thinking",
                    graph_context=True,
                    recency_bias=0.8,
                )
            ),
            _with_retry(
                lambda: client.recall.full_recall(
                    tenant_id=TENANT_ID,
                    query=f"{contact_name} {company} relationship context email transcript",
                    max_results=8,
                    mode="thinking",
                    graph_context=True,
                    recency_bias=0.7,
                    metadata_filters={"company": company} if company else None,
                )
            ),
        )
    except Exception as exc:
        return f"HydraDB recall failed: {_error_payload(exc)}"

    return _format_recall_context(prefs, knowledge)


def _format_recall_context(prefs: dict[str, Any], knowledge: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("=== PREFERENCES & STANCE ===")
    prefs_plain = _to_plain_data(prefs)
    prefs_chunks = prefs_plain.get("chunks") or []
    for c in prefs_chunks:
        text = c.get("chunk_content") or c.get("text", "")
        score = c.get("relevancy_score", "")
        if text:
            lines.append(f"  [relevancy={score}] {text[:500]}")
    if not prefs_chunks:
        lines.append("  (no preferences data)")

    lines.append("")
    lines.append("=== KNOWLEDGE & CONTEXT ===")
    know_plain = _to_plain_data(knowledge)
    know_chunks = know_plain.get("chunks") or []
    for c in know_chunks:
        text = c.get("chunk_content") or c.get("text", "")
        score = c.get("relevancy_score", "")
        if text:
            lines.append(f"  [relevancy={score}] {text[:500]}")
    if not know_chunks:
        lines.append("  (no knowledge data)")

    return "\n".join(lines)[:12000]


def _fallback_brief(contact_name: str, company: str, context: str) -> dict[str, Any]:
    return {
        "contactName": contact_name,
        "company": company,
        "currentStance": "neutral",
        "stanceShiftNote": "No confirmed recent stance shift. Treat open questions as active risk.",
        "topConcerns": ["Security review", "rollout workload", "budget timing"],
        "communicationStyle": "Use compact written summaries with owners, dates, and explicit asks.",
        "talkingPoints": [
            "Confirm the current approval owner.",
            "Ask which risk would block the next step.",
            "Close with one dated follow-up.",
        ],
        "landmines": ["Do not assume procurement is aligned.", "Avoid vague implementation language."],
        "lastInteraction": context[:180],
        "powerNote": "HydraDB recall is empty or unavailable; this brief is a conservative default.",
    }
