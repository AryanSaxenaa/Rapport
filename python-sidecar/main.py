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
        # Strategy 1: Try full_recall with contact-related queries
        for q in ["contact", "email", "meeting", "interaction"]:
            try:
                root_data = await _with_retry(
                    lambda q=q: client.recall.full_recall(
                        tenant_id=TENANT_ID,
                        query=q,
                        max_results=30,
                        mode="thinking",
                        graph_context=True,
                        recency_bias=0.0,
                    )
                )
                root_plain = _to_plain_data(root_data)
                memories = root_plain.get("memories") or root_plain.get("results") or []
                for mem in memories:
                    meta = mem.get("metadata") or {}
                    email = meta.get("contact_email", "")
                    if email and email not in seen:
                        seen.add(email)
                        extracted = mem.get("additional_metadata", {}).get("extracted", {})
                        contacts.append({
                            "contactEmail": email,
                            "contactName": meta.get("contact_name", email.split("@")[0]),
                            "company": meta.get("company", ""),
                            "stance": meta.get("stance") or extracted.get("stance", "neutral"),
                            "lastInteraction": meta.get("interaction_date", ""),
                            "topics": meta.get("topics_raised", []),
                        })
            except Exception:
                pass

        # Strategy 2: Try recall_preferences on the default sub-tenant for a broad search
        try:
            pref_data = await _with_retry(
                lambda: client.recall.recall_preferences(
                    tenant_id=TENANT_ID,
                    sub_tenant_id="_contacts_manifest",
                    query="contact",
                    max_results=50,
                    mode="thinking",
                    graph_context=True,
                    recency_bias=0.0,
                )
            )
            pref_plain = _to_plain_data(pref_data)
            manifests = pref_plain.get("memories") or pref_plain.get("results") or []
            for man in manifests:
                meta = man.get("metadata") or {}
                email = meta.get("contact_email", "")
                if email and email not in seen:
                    seen.add(email)
                    contacts.append({
                        "contactEmail": email,
                        "contactName": meta.get("contact_name", email.split("@")[0]),
                        "company": meta.get("company", ""),
                        "stance": "neutral",
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
