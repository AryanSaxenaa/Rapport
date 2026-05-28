from entity_extractor import extract_entities_safe, has_meaningful_extraction
from hydradb_client import write_interaction_to_hydradb, _hydradb_client
from relationship_graph import store_relations


async def process_interaction(
    text: str,
    contact_email: str | None,
    contact_name: str | None,
    company: str | None,
    interaction_type: str,
) -> str | None:
    """Process an interaction and return an error message on failure, None on success."""
    extracted, error = await extract_entities_safe(text)
    if error:
        return error

    if not has_meaningful_extraction(extracted):
        return None

    await write_interaction_to_hydradb(
        contact_email=contact_email,
        contact_name=contact_name,
        company=company,
        extracted=extracted,
        interaction_type=interaction_type,
        raw_text=text,
    )

    client = _hydradb_client()
    if client:
        try:
            await store_relations(client, extracted.get("relations") or [], contact_email)
        except Exception as exc:
            print(f"Ingestion pipeline: store_relations failed (non-fatal) — {exc}")

    return None
