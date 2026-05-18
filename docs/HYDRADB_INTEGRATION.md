# HydraDB Integration

## Integration Summary

Rapport uses HydraDB as its durable relationship memory and recall layer. The FastAPI sidecar integrates through the official Python SDK:

```python
from hydra_db import AsyncHydraDB

client = AsyncHydraDB(token=os.environ["HYDRA_DB_API_KEY"])
```

The current implementation lives in:

```text
python-sidecar/hydradb_client.py
```

## Why The Python SDK

Rapport keeps memory operations in the backend sidecar rather than the Electron renderer. This keeps API keys out of the frontend, lets FastAPI handle async workflows cleanly, and aligns with the sidecar's role as the ingestion and intelligence layer.

The SDK is used for:

- `client.upload.add_memory`
- `client.recall.recall_preferences`
- `client.recall.full_recall`

The wrapper includes exponential backoff for HydraDB retryable errors:

- `429`
- `500`
- `503`

## Tenant Model

Rapport uses one HydraDB tenant per workspace/user.

```text
tenant_id = HYDRA_DB_TENANT_ID
```

Each contact is mapped to a sub-tenant:

```text
mira.voss@northstar-ledger.example
=> mira_voss_at_northstar-ledger_example
```

This gives contact-level memory isolation while allowing account-level knowledge recall across the tenant.

## Memory Writes

Each meeting or email interaction becomes a HydraDB memory.

```python
await client.upload.add_memory(
    tenant_id=TENANT_ID,
    sub_tenant_id=sub_tenant_id,
    memories=[
        {
            "text": content,
            "infer": True,
            "user_name": contact_name,
            "metadata": metadata,
            "additional_metadata": {
                "raw_text": raw_text[:4000],
                "extracted": extracted,
            },
        }
    ],
)
```

`infer: True` is important because the product depends on HydraDB extracting implicit relationship preferences and behavioral signals.

## Metadata Strategy

Rapport stores structured metadata with every interaction:

```json
{
  "contact_email": "mira.voss@northstar-ledger.example",
  "contact_name": "Mira Voss",
  "company": "Northstar Ledger",
  "interaction_type": "call",
  "interaction_date": "2026-05-18",
  "topics_raised": ["security", "rollout", "budget"],
  "sentiment_shift": "neutral->skeptic"
}
```

This metadata lets Rapport filter, rank, and explain recalled context.

## Recall Strategy

Rapport always recalls from two complementary HydraDB surfaces:

```python
prefs, knowledge = await asyncio.gather(
    client.recall.recall_preferences(
        tenant_id=TENANT_ID,
        sub_tenant_id=sub_tenant_id,
        query="contact preferences stance concerns commitments",
        max_results=12,
        mode="thinking",
        graph_context=True,
        recency_bias=0.8,
    ),
    client.recall.full_recall(
        tenant_id=TENANT_ID,
        query="contact company relationship context email transcript",
        max_results=8,
        mode="thinking",
        graph_context=True,
        recency_bias=0.7,
        metadata_filters={"company": company},
    ),
)
```

The split is deliberate:

- `recall_preferences` finds contact-specific behavioral memory.
- `full_recall` finds account-wide knowledge from emails, calls, and documents.

## Why This Matters

A normal vector search can find similar text. Rapport needs more than similarity. It needs relationship continuity:

- repeated concerns
- stance shifts
- decision influence
- preferred communication style
- commitments and deadlines
- political dependencies

HydraDB is a strong fit because it combines memory, knowledge, recall, and graph context under one platform.

## Current Status

Implemented:

- SDK import and client creation
- memory write path
- contact sub-tenant strategy
- parallel recall path
- retry handling
- fallback behavior when env vars are missing

Planned:

- knowledge upload for full transcripts and Gmail threads
- processing verification for uploaded sources
- graph relation fetch for the D3 visualization
- tenant provisioning helper
- richer metadata filters by date, interaction type, and deal stage

## HydraDB Team Feedback Areas

The most useful feedback from HydraDB would be:

- best-practice tenant/sub-tenant modeling for contact-level memory
- recommended metadata schema for relationship intelligence
- whether graph relation fetch should power the UI graph directly
- ideal recall settings for recency-sensitive stance tracking
- expected production limits and batching guidance for call/email ingestion
