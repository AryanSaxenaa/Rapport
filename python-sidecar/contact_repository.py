"""Builds the contacts list from HydraDB sub-tenants and full-recall fallback.

Sub-tenant IDs are treated as opaque tokens. Email is always read from
stored metadata — never decoded from the sub-tenant ID string (lossy).
"""

import asyncio

from contact_persistence import normalize_contact, load_local_contacts
from hydradb_client import (
    TENANT_ID,
    _hydradb_client,
    _to_plain_data,
    _with_retry,
)
from hydra_db import AsyncHydraDB
from sidecar_types import ContactDict, ContactsResponse


def _add_contact(contacts: list[ContactDict], seen: set[str], contact: ContactDict) -> None:
    email = contact.get("contactEmail", "").lower()
    if not email or email in seen:
        return
    seen.add(email)
    contacts.append(contact)


async def _iter_from_sub_tenants(client: AsyncHydraDB) -> list[ContactDict]:
    """Fetch contacts via sub-tenant recall_preferences (parallel)."""
    try:
        raw = await _with_retry(lambda: client.tenant.get_sub_tenant_ids(tenant_id=TENANT_ID))
        all_ids = _to_plain_data(raw).get("sub_tenant_ids") or []
    except Exception:
        return []

    contact_ids = [sid for sid in all_ids if not sid.startswith("_")]
    if not contact_ids:
        return []

    async def recall_one(sid: str) -> ContactDict | None:
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
            meta: dict[str, object] = {}
            for src in sources:
                if not isinstance(src, dict):
                    continue
                m = src.get("additional_metadata") or src.get("metadata") or {}
                if m.get("contact_email"):
                    meta = m
                    break
            if not meta:
                return None
            return _normalize_contact_src(meta)
        except Exception:
            return None

    results = await asyncio.gather(*(recall_one(sid) for sid in contact_ids), return_exceptions=True)
    return [r for r in results if isinstance(r, dict)]


def _normalize_contact_src(meta: dict[str, object]) -> ContactDict:
    extracted = meta.get("extracted")
    extracted = extracted if isinstance(extracted, dict) else {}
    flat: dict[str, object] = {**extracted, **meta}  # type: ignore[arg-type]
    return normalize_contact(flat)


async def _iter_from_full_recall(client: AsyncHydraDB) -> list[ContactDict]:
    """Fallback: full_recall queries when sub-tenant path returns < 2 contacts."""
    contacts: list[ContactDict] = []
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
                    contacts.append(_normalize_contact_src(meta))
        except Exception as exc:
            print(f"Contact repo: full_recall query '{query}' failed — {exc}")
    return contacts


async def fetch_contacts() -> ContactsResponse:
    """Return contacts from HydraDB with local persistence as a cache layer.
    Returns an empty contacts array with an informative error when HydraDB
    is unreachable or unconfigured.
    """
    client = _hydradb_client()

    if not client:
        return ContactsResponse(
            contacts=load_local_contacts(),
            source="local",
            error="HydraDB API key not configured.",
        )

    contacts: list[ContactDict] = []
    seen: set[str] = set()

    # Seed with local cache so previously-ingested contacts are always visible.
    for c in load_local_contacts():
        _add_contact(contacts, seen, c)

    try:
        for c in await _iter_from_sub_tenants(client):
            _add_contact(contacts, seen, c)

        if len(contacts) < 2:
            for c in await _iter_from_full_recall(client):
                _add_contact(contacts, seen, c)
    except Exception as exc:
        if contacts:
            return ContactsResponse(contacts=contacts, source="local", error=f"HydraDB query failed: {exc}")
        return ContactsResponse(source="hydradb", error=f"HydraDB query failed: {exc}")

    if not contacts:
        return ContactsResponse(
            source="hydradb",
            warning="No contacts found in HydraDB. Ingest emails or start a recording to populate your relationship graph.",
        )

    return ContactsResponse(contacts=contacts, source="hydradb")
