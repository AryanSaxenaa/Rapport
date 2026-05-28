import asyncio
import json
from html_utils import strip_json_fences
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
from sidecar_types import BriefDict

_BRIEF_MODELS = parse_model_list("BRIEF_MODEL", "openrouter/owl-alpha,poolside/laguna-m.1:free")


class BriefGenerationError(Exception):
    def __init__(self, message: str, error_type: str = "brief_failed"):
        super().__init__(message)
        self.error_type = error_type


async def generate_pre_call_brief(contact_email: str, contact_name: str, company: str) -> BriefDict:
    context = await _recall_contact_context(contact_email, contact_name, company)
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
    content = extract_content(response)
    if not content.strip():
        raise BriefGenerationError("Brief model returned an empty response.", "empty_response")
    try:
        return json.loads(strip_json_fences(content))
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise BriefGenerationError(
            f"Brief model returned invalid data: {exc}",
            "malformed_response",
        ) from exc


async def generate_pre_call_brief_safe(contact_email: str, contact_name: str, company: str) -> tuple[BriefDict | None, str | None]:
    """Non-raising wrapper: returns (brief_or_none, error_message_or_none)."""
    try:
        brief = await generate_pre_call_brief(contact_email, contact_name, company)
        return brief, None
    except BriefGenerationError as exc:
        return None, str(exc)


async def _recall_contact_context(contact_email: str, contact_name: str, company: str) -> str:
    if not API_KEY:
        return "No HydraDB context available — API key not configured."

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


def _format_recall_context(prefs: dict[str, object], knowledge: dict[str, object]) -> str:
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



