import asyncio
from contextlib import suppress
from typing import Any

from dotenv import load_dotenv

# Load .env BEFORE any local imports that read env vars
load_dotenv(override=True)

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from audio_capture import AudioCapture
from calendar_poller import poll_for_upcoming_meetings
from entity_extractor import extract_entities
from gmail_reader import fetch_recent_emails
from hydradb_client import generate_pre_call_brief, write_interaction_to_hydradb, recall_contact_context, TENANT_ID
from hydradb_client import demo_contacts, load_local_contacts
from hydradb_client import _hydradb_client, _sub_tenant_id, _with_retry, _to_plain_data

app = FastAPI(title="Rapport Sidecar", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

connected_clients: list[WebSocket] = []
recording_session: dict[str, Any] = {"active": False, "buffer": [], "contact": None, "capture": None}


@app.get("/health")
async def health():
    return {"status": "online", "service": "rapport-sidecar"}


@app.websocket("/ws/transcript")
async def transcript_ws(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        with suppress(ValueError):
            connected_clients.remove(websocket)


async def push_event(payload: dict[str, Any]):
    for ws in connected_clients[:]:
        try:
            await ws.send_json(payload)
        except Exception:
            with suppress(ValueError):
                connected_clients.remove(ws)


async def push_transcript(text: str):
    await push_event({"type": "transcript", "text": text})


@app.post("/recording/start")
async def start_recording(body: dict[str, Any]):
    recording_session["active"] = True
    recording_session["contact"] = body
    recording_session["buffer"] = []

    async def on_text(text: str):
        recording_session["buffer"].append(text)
        await push_transcript(text)
        if len(recording_session["buffer"]) % 5 == 0:
            context_block = " ".join(recording_session["buffer"][-10:])
            asyncio.create_task(_extract_and_store(context_block))

    capture = AudioCapture(on_text)
    recording_session["capture"] = capture
    capture.start()
    await push_transcript("Recording started. Waiting for audio chunks.")
    return {"status": "recording"}


async def _extract_and_store(text: str):
    contact = recording_session.get("contact")
    if not contact:
        return

    extracted = await extract_entities(text)
    await write_interaction_to_hydradb(
        contact_email=contact.get("contactEmail") or contact.get("contact_email"),
        contact_name=contact.get("contactName") or contact.get("contact_name"),
        company=contact.get("company"),
        extracted=extracted,
        interaction_type="call",
        raw_text=text,
    )


@app.post("/recording/stop")
async def stop_recording():
    recording_session["active"] = False
    capture = recording_session.get("capture")
    if capture:
        capture.stop()

    if recording_session["buffer"] and recording_session["contact"]:
        full_text = " ".join(recording_session["buffer"])
        await _extract_and_store(full_text)

    await push_transcript("Recording stopped. Session memory update queued.")
    return {"status": "stopped"}


@app.get("/contacts")
async def list_contacts():
    """Return stored contacts from HydraDB memory graph."""
    def add_contact(
        contacts: list[dict[str, Any]],
        seen: set[str],
        contact: dict[str, Any],
    ) -> None:
        email = (contact.get("contactEmail") or contact.get("contact_email") or "").strip()
        if not email or email.lower() in seen:
            return
        seen.add(email.lower())
        contacts.append({
            "contactEmail": email,
            "contactName": contact.get("contactName") or contact.get("contact_name") or email.split("@")[0].replace(".", " ").title(),
            "company": contact.get("company") or "",
            "stance": contact.get("stance") or "neutral",
            "lastInteraction": contact.get("lastInteraction") or contact.get("interaction_date") or "",
            "topics": contact.get("topics") or contact.get("topics_raised") or [],
        })

    def contact_from_sub_id(sub_id: str) -> dict[str, Any]:
        email = sub_id.replace("_at_", "@").replace("_", ".")
        return {
            "contactEmail": email,
            "contactName": email.split("@")[0].replace(".", " ").title(),
            "company": "",
            "stance": "neutral",
            "lastInteraction": "",
            "topics": [],
        }

    def contact_from_sources(sub_id: str, sources: list[dict[str, Any]]) -> dict[str, Any]:
        contact = contact_from_sub_id(sub_id)
        for src in sources:
            meta = src.get("additional_metadata") or src.get("metadata") or {}
            extracted = meta.get("extracted") if isinstance(meta.get("extracted"), dict) else {}
            contact["contactEmail"] = contact["contactEmail"] if contact["contactEmail"] else meta.get("contact_email", "")
            contact["contactName"] = meta.get("contact_name") or contact["contactName"]
            contact["company"] = meta.get("company") or contact["company"]
            contact["lastInteraction"] = meta.get("interaction_date") or contact["lastInteraction"]
            contact["topics"] = meta.get("topics_raised") or extracted.get("topics") or contact["topics"]
            contact["stance"] = meta.get("stance") or extracted.get("stance") or contact["stance"]
        return contact

    local_contacts = load_local_contacts()
    client = _hydradb_client()
    if not client:
        return {"contacts": local_contacts or demo_contacts(), "source": "local" if local_contacts else "demo", "warning": "HydraDB API key is not configured."}

    contacts: list[dict[str, Any]] = []
    seen: set[str] = set()
    for contact in local_contacts:
        add_contact(contacts, seen, contact)

    try:
        # Get all sub-tenant IDs (1 call)
        try:
            sub_tenants = await _with_retry(
                lambda: client.tenant.get_sub_tenant_ids(tenant_id=TENANT_ID)
            )
            sub_plain = _to_plain_data(sub_tenants)
            sub_ids = sub_plain.get("sub_tenant_ids") or []
        except Exception:
            sub_ids = []

        # Filter to contact-like sub-tenants (skip internal ones)
        contact_sub_ids = [sid for sid in sub_ids if not sid.startswith("_")]

        # Call recall_preferences on ALL sub-tenants IN PARALLEL with per-call timeout
        async def recall_sub_tenant(sid: str) -> dict | None:
            try:
                pref_data = await _with_retry(
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
                return _to_plain_data(pref_data)
            except Exception:
                return None

        if contact_sub_ids:
            # Use gather with a timeout per task
            results = await asyncio.gather(
                *(recall_sub_tenant(sid) for sid in contact_sub_ids),
                return_exceptions=True,
            )

            for sub_id, result in zip(contact_sub_ids, results):
                if sub_id.lower() in seen:
                    continue
                if isinstance(result, Exception) or not result:
                    add_contact(contacts, seen, contact_from_sub_id(sub_id))
                    continue

                pref_plain = result
                sources = pref_plain.get("sources") or []
                add_contact(contacts, seen, contact_from_sources(sub_id, sources))

        if len(contacts) < 2:
            for query in ("contact", "email interaction", "meeting transcript"):
                try:
                    root_data = await _with_retry(
                        lambda q=query: client.recall.full_recall(
                            tenant_id=TENANT_ID,
                            query=q,
                            max_results=20,
                            mode="fast",
                            graph_context=False,
                            recency_bias=0.0,
                        )
                    )
                    root_plain = _to_plain_data(root_data)
                    chunks = root_plain.get("chunks") or []
                    sources = root_plain.get("sources") or []
                    source_map = {s.get("id"): s for s in sources if s.get("id")}
                    for chunk in chunks:
                        source_id = chunk.get("source_id") or chunk.get("id")
                        source = source_map.get(source_id, {})
                        meta = source.get("additional_metadata") or source.get("metadata") or {}
                        if not meta and isinstance(chunk.get("metadata"), dict):
                            meta = chunk["metadata"]
                        add_contact(contacts, seen, {
                            "contactEmail": meta.get("contact_email", ""),
                            "contactName": meta.get("contact_name", ""),
                            "company": meta.get("company", ""),
                            "stance": meta.get("stance", "neutral"),
                            "lastInteraction": meta.get("interaction_date", ""),
                            "topics": meta.get("topics_raised", []),
                        })
                except Exception:
                    pass

        if contacts:
            return {"contacts": contacts, "source": "hydradb"}
        return {"contacts": demo_contacts(), "source": "demo", "warning": "No contacts were found in HydraDB yet."}
    except Exception as exc:
        fallback = local_contacts or demo_contacts()
        return {"contacts": fallback, "source": "local" if local_contacts else "demo", "error": str(exc)}


@app.get("/brief/{contact_email}")
async def get_brief(contact_email: str, contact_name: str, company: str):
    return await generate_pre_call_brief(contact_email, contact_name, company)


@app.post("/ingest/emails")
async def ingest_emails_endpoint():
    asyncio.create_task(ingest_emails_background())
    return {"status": "ingestion started"}


async def ingest_emails_background():
    emails = fetch_recent_emails(days_back=90)
    for email in emails:
        contact = email.get("contact", {})
        extracted = await extract_entities(email.get("body", ""))
        await write_interaction_to_hydradb(
            contact_email=contact.get("email", "unknown@example.com"),
            contact_name=contact.get("name", "Unknown contact"),
            company=contact.get("company", "Unknown company"),
            extracted=extracted,
            interaction_type="email",
            raw_text=email.get("body", ""),
        )


@app.on_event("startup")
async def startup():
    async def on_upcoming_meeting(meeting_info: dict[str, Any]):
        brief = await generate_pre_call_brief(
            contact_email=meeting_info["contact_email"],
            contact_name=meeting_info["contact_name"],
            company=meeting_info["company"],
        )
        await push_event({"type": "brief", "data": {**brief, "trigger": "calendar"}})

    asyncio.create_task(poll_for_upcoming_meetings(on_upcoming_meeting))
