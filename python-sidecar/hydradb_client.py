import os
import asyncio
import json
from datetime import date
from pathlib import Path
from typing import Any

import httpx
from hydra_db import AsyncHydraDB
from hydra_db.core import ApiError


TENANT_ID = os.getenv("HYDRA_DB_TENANT_ID") or os.getenv("HYDRADB_TENANT_ID") or "orb"
API_KEY = os.getenv("HYDRA_DB_API_KEY") or os.getenv("HYDRADB_API_KEY")
RETRYABLE_STATUS_CODES = {429, 500, 503}


def parse_model_list(env_var: str, default: str) -> list[str]:
    """Return a list of model IDs from a comma-separated env var."""
    return [m.strip() for m in (os.getenv(env_var) or default).split(",") if m.strip()]


_BRIEF_MODELS = parse_model_list("BRIEF_MODEL", "openrouter/owl-alpha,poolside/laguna-m.1:free")
LOCAL_CONTACTS_PATH = Path(__file__).parent / "rapport_contacts.json"


def _sub_tenant_id(contact_email: str | None) -> str:
    value = contact_email or "unknown"
    return value.replace("@", "_at_").replace(".", "_")


def _hydradb_client() -> AsyncHydraDB | None:
    if not API_KEY:
        return None
    return AsyncHydraDB(token=API_KEY)


def _normalise_contact(contact: dict[str, Any]) -> dict[str, Any]:
    email = (contact.get("contactEmail") or contact.get("contact_email") or "").strip()
    name = (contact.get("contactName") or contact.get("contact_name") or "").strip()
    company = (contact.get("company") or "").strip()
    return {
        "contactEmail": email,
        "contactName": name or (email.split("@")[0].replace(".", " ").title() if email else "Unknown contact"),
        "company": company,
        "stance": contact.get("stance") or "neutral",
        "lastInteraction": contact.get("lastInteraction") or contact.get("interaction_date") or "",
        "topics": contact.get("topics") or contact.get("topics_raised") or [],
    }


def load_local_contacts() -> list[dict[str, Any]]:
    if not LOCAL_CONTACTS_PATH.exists():
        return []
    try:
        raw = json.loads(LOCAL_CONTACTS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    contacts = raw if isinstance(raw, list) else raw.get("contacts", [])
    return [_normalise_contact(c) for c in contacts if isinstance(c, dict)]


def save_local_contact(contact: dict[str, Any]) -> None:
    normalised = _normalise_contact(contact)
    if not normalised["contactEmail"]:
        return

    contacts = load_local_contacts()
    by_email = {c["contactEmail"].lower(): c for c in contacts}
    existing = by_email.get(normalised["contactEmail"].lower(), {})
    by_email[normalised["contactEmail"].lower()] = {**existing, **normalised}

    LOCAL_CONTACTS_PATH.write_text(
        json.dumps({"contacts": list(by_email.values())}, indent=2),
        encoding="utf-8",
    )


def demo_contacts() -> list[dict[str, Any]]:
    return [
        {
            "contactEmail": "mira.voss@northstar-ledger.example",
            "contactName": "Mira Voss",
            "company": "Northstar Ledger",
            "stance": "skeptic",
            "lastInteraction": date.today().isoformat(),
            "topics": ["security review", "rollout workload", "budget timing"],
        },
        {
            "contactEmail": "jon.bell@apexfoundry.example",
            "contactName": "Jon Bell",
            "company": "Apex Foundry",
            "stance": "champion",
            "lastInteraction": date.today().isoformat(),
            "topics": ["pilot scope", "executive sponsor"],
        },
    ]


async def _with_retry(operation, max_retries: int = 3):
    for attempt in range(1, max_retries + 1):
        try:
            return await operation()
        except ApiError as exc:
            status_code = getattr(exc, "status_code", None)
            if status_code not in RETRYABLE_STATUS_CODES or attempt == max_retries:
                raise
            await asyncio.sleep(2**attempt)
    raise RuntimeError("HydraDB retry loop exhausted")


def _error_payload(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, ApiError):
        body = getattr(exc, "body", None)
        detail = body.get("detail") if isinstance(body, dict) else None
        return {
            "status_code": getattr(exc, "status_code", None),
            "error_code": detail.get("error_code") if isinstance(detail, dict) else None,
            "message": detail.get("message") if isinstance(detail, dict) else str(exc),
        }
    return {"message": str(exc)}


async def write_interaction_to_hydradb(
    contact_email: str | None,
    contact_name: str | None,
    company: str | None,
    extracted: dict[str, Any],
    interaction_type: str,
    raw_text: str,
) -> dict[str, Any]:
    content = (
        f"{contact_name or 'Unknown contact'} at {company or 'Unknown company'}: "
        f"{extracted.get('summary') or raw_text[:800]}"
    )
    metadata = {
        "contact_email": contact_email,
        "contact_name": contact_name,
        "company": company,
        "interaction_type": interaction_type,
        "interaction_date": date.today().isoformat(),
        "topics_raised": extracted.get("topics", []),
        "sentiment_shift": extracted.get("sentiment_shift"),
    }
    save_local_contact({
        "contactEmail": contact_email or "",
        "contactName": contact_name or "",
        "company": company or "",
        "stance": extracted.get("stance") or "neutral",
        "lastInteraction": metadata["interaction_date"],
        "topics": metadata["topics_raised"],
    })

    if not API_KEY:
        return {"status": "skipped", "reason": "HYDRA_DB_API_KEY missing", "content": content, "metadata": metadata}

    client = _hydradb_client()
    if not client:
        return {"status": "skipped", "reason": "HydraDB client unavailable"}
    try:
        result = await _with_retry(
            lambda: client.upload.add_memory(
                tenant_id=TENANT_ID,
                sub_tenant_id=_sub_tenant_id(contact_email),
                memories=[
                    {
                        "text": content,
                        "infer": True,
                        "user_name": contact_name or contact_email or "unknown_contact",
                        "metadata": metadata,
                        "additional_metadata": {
                            "raw_text": raw_text[:4000],
                            "extracted": extracted,
                        },
                    }
                ],
            )
        )

        # Also write to a contacts manifest for reliable discovery
        if contact_email:
            manifest_meta = {
                "contact_email": contact_email,
                "contact_name": contact_name or "",
                "company": company or "",
                "interaction_date": date.today().isoformat(),
            }
            try:
                await _with_retry(
                    lambda: client.upload.add_memory(
                        tenant_id=TENANT_ID,
                        sub_tenant_id="_contacts_manifest",
                        memories=[{
                            "text": f"Contact: {contact_name or contact_email} at {company or 'unknown'}",
                            "infer": True,
                            "user_name": contact_name or contact_email or "unknown",
                            "metadata": manifest_meta,
                        }],
                    )
                )
            except Exception:
                pass  # manifest write is best-effort

    except Exception as exc:
        return {"status": "error", "transport": "python-sdk", "error": _error_payload(exc)}
    return {"status": "ok", "transport": "python-sdk", "data": _to_plain_data(result)}


async def generate_pre_call_brief(contact_email: str, contact_name: str, company: str) -> dict[str, Any]:
    context = await recall_contact_context(contact_email, contact_name, company)
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return fallback_brief(contact_name, company, context)

    prompt = f"""
Create a pre-call brief as JSON for {contact_name} at {company}.
Use this recalled context:
{context}

Return keys: contactName, company, currentStance, stanceShiftNote, topConcerns,
communicationStyle, talkingPoints, landmines, lastInteraction, powerNote.
"""
    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "https://rapport.local",
                "X-Title": "Rapport",
            },
            json={
                "models": _BRIEF_MODELS,
                "temperature": 0.2,
                "max_tokens": 1500,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        response.raise_for_status()
        try:
            return json.loads(response.json()["choices"][0]["message"]["content"])
        except Exception:
            return fallback_brief(contact_name, company, context)


async def recall_contact_context(contact_email: str, contact_name: str, company: str) -> str:
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
            )
        )
    except Exception as exc:
        return f"HydraDB recall failed: {_error_payload(exc)}"

    return _format_recall_context(prefs, knowledge)


def _to_plain_data(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "dict"):
        return value.dict()
    return value


def _format_recall_context(prefs: Any, knowledge: Any) -> str:
    """Extract clean text from HydraDB's chunk/source response format."""
    lines = []
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


def fallback_brief(contact_name: str, company: str, context: str) -> dict[str, Any]:
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
            "Close with one dated follow-up."
        ],
        "landmines": ["Do not assume procurement is aligned.", "Avoid vague implementation language."],
        "lastInteraction": context[:180],
        "powerNote": "HydraDB recall is empty or unavailable; this brief is a conservative default.",
    }
