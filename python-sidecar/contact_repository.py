"""Builds the contacts list from HydraDB sub-tenants and full-recall fallback.

Sub-tenant IDs are treated as opaque tokens. Email is always read from
stored metadata — never decoded from the sub-tenant ID string (lossy).
"""

import asyncio
from typing import Any

from hydradb_client import (
    TENANT_ID,
    _hydradb_client,
    _to_plain_data,
    _with_retry,
    load_local_contacts,
    demo_contacts,
)


def normalize_contact(meta: dict[str, Any], fallback_email: str = "") -> dict[str, Any]:
    """Canonical contact shape from any metadata dict."""
    extracted = meta.get("extracted") if isinstance(meta.get("extracted"), dict) else {}
    email = (meta.get("contact_email") or meta.get("contactEmail") or fallback_email).strip()
    name = (meta.get("contact_name") or meta.get("contactName") or "").strip()
    return {
        "contactEmail": email,
        "contactName": name or (email.split("@")[0].replace(".", " ").title() if email else "Unknown"),
        "company": (meta.get("company") or "").strip(),
        "stance": meta.get("stance") or extracted.get("stance") or "neutral",
        "lastInteraction": meta.get("interaction_date") or meta.get("lastInteraction") or "",
        "topics": meta.get("topics_raised") or extracted.get("topics") or [],
        "sentimentShift": meta.get("sentiment_shift") or extracted.get("sentiment_shift") or "",
        "commitments": extracted.get("commitments") or [],
        "unresolved": extracted.get("unresolved") or [],
        "summary": extracted.get("summary") or "",
    }


def _add_contact(contacts: list[dict[str, Any]], seen: set[str], contact: dict[str, Any]) -> None:
    email = contact.get("contactEmail", "").lower()
    if not email or email in seen:
        return
    seen.add(email)
    contacts.append(contact)


async def _iter_from_sub_tenants(client) -> list[dict[str, Any]]:
    """Fetch contacts via sub-tenant recall_preferences (parallel)."""
    try:
        raw = await _with_retry(lambda: client.tenant.get_sub_tenant_ids(tenant_id=TENANT_ID))
        all_ids = _to_plain_data(raw).get("sub_tenant_ids") or []
    except Exception:
        return []

    contact_ids = [sid for sid in all_ids if not sid.startswith("_")]
    if not contact_ids:
        return []

    async def recall_one(sid: str) -> dict[str, Any] | None:
        try:
            data = await _with_retry(
                lambda s=sid: client.recall.recall_preferences(
                    tenant_id=TENANT_ID,
                    sub_tenant_id=s,
                    query="contact",
                    max_results=3,
                    mode="fast",
                    graph_context=False,
                    recency_bias=0.0,
                )
            )
            plain = _to_plain_data(data)
            sources = plain.get("sources") or []
            # Build contact from stored metadata; never decode sid as email
            meta: dict[str, Any] = {}
            for src in sources:
                m = src.get("additional_metadata") or src.get("metadata") or {}
                if m.get("contact_email"):
                    meta = m
                    break
            if not meta:
                return None
            return normalize_contact(meta)
        except Exception:
            return None

    results = await asyncio.gather(*(recall_one(sid) for sid in contact_ids), return_exceptions=True)
    return [r for r in results if isinstance(r, dict)]


async def _iter_from_full_recall(client) -> list[dict[str, Any]]:
    """Fallback: full_recall queries when sub-tenant path returns < 2 contacts."""
    contacts: list[dict[str, Any]] = []
    for query in ("contact", "email interaction", "meeting transcript"):
        try:
            data = await _with_retry(
                lambda q=query: client.recall.full_recall(
                    tenant_id=TENANT_ID,
                    query=q,
                    max_results=20,
                    mode="fast",
                    graph_context=False,
                    recency_bias=0.0,
                )
            )
            plain = _to_plain_data(data)
            chunks = plain.get("chunks") or []
            sources = plain.get("sources") or []
            source_map = {s.get("id"): s for s in sources if s.get("id")}
            for chunk in chunks:
                source = source_map.get(chunk.get("source_id") or chunk.get("id"), {})
                meta = source.get("additional_metadata") or source.get("metadata") or {}
                if not meta and isinstance(chunk.get("metadata"), dict):
                    meta = chunk["metadata"]
                if meta.get("contact_email"):
                    contacts.append(normalize_contact(meta))
        except Exception:
            pass
    return contacts


async def fetch_contacts() -> dict[str, Any]:
    """Return contacts from HydraDB with local/demo fallback."""
    local = load_local_contacts()
    client = _hydradb_client()

    if not client:
        return {
            "contacts": local or demo_contacts(),
            "source": "local" if local else "demo",
            "warning": "HydraDB API key not configured.",
        }

    contacts: list[dict[str, Any]] = []
    seen: set[str] = set()

    for c in local:
        _add_contact(contacts, seen, c)

    try:
        for c in await _iter_from_sub_tenants(client):
            _add_contact(contacts, seen, c)

        if len(contacts) < 2:
            for c in await _iter_from_full_recall(client):
                _add_contact(contacts, seen, c)

        if contacts:
            return {"contacts": contacts, "source": "hydradb"}
        return {"contacts": demo_contacts(), "source": "demo", "warning": "No contacts in HydraDB yet."}

    except Exception as exc:
        fallback = local or demo_contacts()
        return {"contacts": fallback, "source": "local" if local else "demo", "error": str(exc)}
