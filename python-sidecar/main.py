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
    client = _hydradb_client()
    if not client:
        return {"contacts": [], "source": "unavailable"}

    contacts: list[dict[str, Any]] = []
    seen: set[str] = set()

    try:
        # Strategy 1: List all sub-tenants to discover contacts
        try:
            sub_tenants = await _with_retry(
                lambda: client.tenant.get_sub_tenant_ids(tenant_id=TENANT_ID)
            )
            sub_plain = _to_plain_data(sub_tenants)
            sub_ids = sub_plain.get("sub_tenant_ids") or []
        except Exception:
            sub_ids = []

        # Strategy 2: For each contact-like sub-tenant, recall preferences to get details
        for sub_id in sub_ids:
            if sub_id.startswith("_"):
                continue  # skip internal sub-tenants
            if sub_id in seen:
                continue
            seen.add(sub_id)
            try:
                pref_data = await _with_retry(
                    lambda sid=sub_id: client.recall.recall_preferences(
                        tenant_id=TENANT_ID,
                        sub_tenant_id=sid,
                        query="contact",
                        max_results=3,
                        mode="thinking",
                        graph_context=False,
                        recency_bias=0.0,
                    )
                )
                pref_plain = _to_plain_data(pref_data)
                chunks = pref_plain.get("chunks") or []
                sources = pref_plain.get("sources") or []

                # Build source lookup
                source_map = {s.get("id"): s for s in sources if s.get("id")}

                email = ""
                name = ""
                company = ""
                last_interaction = ""
                topics = []

                # Extract from sources (has additional_metadata)
                for src in sources:
                    meta = src.get("additional_metadata") or {}
                    if not email:
                        email = meta.get("contact_email", "") or sub_id.replace("_at_", "@").replace("_", ".")
                    if not name:
                        name = meta.get("contact_name", "")
                    if not company:
                        company = meta.get("company", "")
                    if not last_interaction:
                        last_interaction = meta.get("interaction_date", "")
                    if not topics:
                        topics = meta.get("topics_raised", [])

                # Fallback: extract email from sub-tenant ID
                if not email:
                    email = sub_id.replace("_at_", "@").replace("_", ".")
                if not name:
                    name = email.split("@")[0].replace(".", " ").title()

                if email not in seen:
                    seen.add(email)
                    contacts.append({
                        "contactEmail": email,
                        "contactName": name,
                        "company": company,
                        "stance": "neutral",
                        "lastInteraction": last_interaction,
                        "topics": topics,
                    })
            except Exception:
                # Fallback: just use sub-tenant ID as contact identifier
                email = sub_id.replace("_at_", "@").replace("_", ".")
                if email not in seen:
                    seen.add(email)
                    contacts.append({
                        "contactEmail": email,
                        "contactName": email.split("@")[0].replace(".", " ").title(),
                        "company": "",
                        "stance": "neutral",
                        "lastInteraction": "",
                        "topics": [],
                    })

        # Strategy 3: Try full_recall for any remaining contacts not in sub-tenant list
        if len(contacts) < 5:
            for q in ["contact", "email", "meeting", "interaction"]:
                try:
                    root_data = await _with_retry(
                        lambda q=q: client.recall.full_recall(
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
                        src = source_map.get(source_id, {})
                        meta = src.get("additional_metadata") or {}
                        email = meta.get("contact_email", "")
                        if email and email not in seen:
                            seen.add(email)
                            contacts.append({
                                "contactEmail": email,
                                "contactName": meta.get("contact_name", email.split("@")[0]),
                                "company": meta.get("company", ""),
                                "stance": meta.get("stance", "neutral"),
                                "lastInteraction": meta.get("interaction_date", ""),
                                "topics": meta.get("topics_raised", []),
                            })
                except Exception:
                    pass

        return {"contacts": contacts, "source": "hydradb"}
    except Exception as exc:
        return {"contacts": [], "source": "error", "error": str(exc)}


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
