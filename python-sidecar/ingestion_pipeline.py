from contextlib import suppress

from entity_extractor import extract_entities, has_meaningful_extraction
from hydradb_client import write_interaction_to_hydradb
from relationship_graph import store_relations


async def process_interaction(
    text: str,
    contact_email: str | None,
    contact_name: str | None,
    company: str | None,
    interaction_type: str,
) -> None:
    extracted = await extract_entities(text)
    if not has_meaningful_extraction(extracted):
        return

    await write_interaction_to_hydradb(
        contact_email=contact_email,
        contact_name=contact_name,
        company=company,
        extracted=extracted,
        interaction_type=interaction_type,
        raw_text=text,
    )

    from hydradb_client import _hydradb_client

    client = _hydradb_client()
    if client:
        with suppress(Exception):
            await store_relations(client, extracted.get("relations") or [], contact_email)
