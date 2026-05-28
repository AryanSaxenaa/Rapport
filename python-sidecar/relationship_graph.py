from datetime import date
from typing import Any

from hydra_db import AsyncHydraDB
from hydradb_client import TENANT_ID, _hydradb_client, _with_retry, _to_plain_data
from sidecar_types import RelationEntry, GraphData


VALID_TYPES = frozenset({
    "approves", "blocks", "escalates_to", "influences",
    "committed_to", "awaits_from", "endorsed_by",
})


def _edge_color(rel_type: str) -> str:
    if rel_type in ("blocks", "awaits_from"):
        return "red"
    if rel_type in ("committed_to", "approves"):
        return "amber"
    if rel_type in ("influences", "endorsed_by"):
        return "green"
    return "grey"


async def store_relations(
    client: AsyncHydraDB | None,
    relations: list[RelationEntry],
    contact_email: str | None,
    interaction_date: str | None = None,
) -> None:
    """Store each extracted relation as a typed memory in the _relations sub-tenant.

    The LLM extraction prompt produces keys ``from`` / ``to`` / ``type`` /
    ``evidence`` / ``confidence``.  We also accept the TypedDict aliases
    ``from_person`` / ``to_person`` so either schema works.
    """
    if not relations or not client:
        return

    today = interaction_date or date.today().isoformat()
    memories = []
    for rel in relations:
        # Accept both the prompt-style keys ('from'/'to') and the TypedDict
        # aliases ('from_person'/'to_person') — whichever the LLM returns.
        from_p = (rel.get("from") or rel.get("from_person") or "").strip()
        to_p   = (rel.get("to")   or rel.get("to_person")   or "").strip()
        rel_type  = (rel.get("type") or "").strip()
        evidence  = (rel.get("evidence") or "").strip()
        confidence = float(rel.get("confidence") or 0.7)

        if not (from_p and to_p and rel_type in VALID_TYPES and evidence):
            continue

        memories.append({
            "text": f"{from_p} {rel_type} {to_p}: {evidence}",
            "infer": False,
            "metadata": {
                "from_person": from_p,
                "to_person": to_p,
                "relation_type": rel_type,
                "evidence_text": evidence,
                "date": today,
                "confidence": confidence,
                "source_contact": contact_email or "",
            },
        })

    if not memories:
        return

    await _with_retry(
        lambda: client.upload.add_memory(
            tenant_id=TENANT_ID,
            sub_tenant_id="_relations",
            memories=memories,
        )
    )


async def build_graph() -> GraphData:
    """Return evidence-backed directed graph from HydraDB _relations sub-tenant."""
    client = _hydradb_client()
    if not client:
        return {"nodes": [], "edges": []}

    try:
        result = await _with_retry(
            lambda: client.recall.recall_preferences(
                tenant_id=TENANT_ID,
                sub_tenant_id="_relations",
                query="blocks approves influences awaits committed endorsed escalates relationship",
                max_results=100,
                mode="fast",
                graph_context=False,
                recency_bias=0.5,
            )
        )
    except Exception:
        return {"nodes": [], "edges": []}

    chunks = _to_plain_data(result).get("chunks") or []

    edges_map: dict[tuple, dict[str, Any]] = {}
    persons: dict[str, dict[str, Any]] = {}

    for chunk in chunks:
        meta = chunk.get("metadata") or {}
        from_p = (meta.get("from_person") or "").strip()
        to_p = (meta.get("to_person") or "").strip()
        rel_type = (meta.get("relation_type") or "").strip()
        evidence = (meta.get("evidence_text") or "").strip()
        chunk_date = (meta.get("date") or "").strip()
        confidence = float(meta.get("confidence") or 0.5)

        if not (from_p and to_p and rel_type in VALID_TYPES):
            continue

        for name in (from_p, to_p):
            if name not in persons:
                persons[name] = {"id": name, "label": name, "importance": 0.0, "type": "person"}

        key = (from_p, to_p, rel_type)
        if key not in edges_map:
            edges_map[key] = {
                "from": from_p,
                "to": to_p,
                "type": rel_type,
                "weight": 0.0,
                "color": _edge_color(rel_type),
                "evidence": [],
            }

        edges_map[key]["weight"] += confidence
        if evidence:
            edges_map[key]["evidence"].append({"quote": evidence, "date": chunk_date})

    # Importance = unresolved items held + decisions influenced + in-degree on approves/escalates_to
    unresolved: dict[str, int] = {}
    decisions: dict[str, int] = {}
    in_degree: dict[str, int] = {}

    for (from_p, to_p, rel_type) in edges_map:
        if rel_type in ("blocks", "awaits_from"):
            unresolved[from_p] = unresolved.get(from_p, 0) + 1
        if rel_type == "influences":
            decisions[from_p] = decisions.get(from_p, 0) + 1
        if rel_type in ("approves", "escalates_to"):
            in_degree[to_p] = in_degree.get(to_p, 0) + 1

    for name, node in persons.items():
        node["importance"] = min(
            1.0,
            0.35 * unresolved.get(name, 0)
            + 0.35 * decisions.get(name, 0)
            + 0.30 * in_degree.get(name, 0),
        )

    return {"nodes": list(persons.values()), "edges": list(edges_map.values())}
