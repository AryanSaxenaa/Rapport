import asyncio
from contextlib import suppress
from typing import Any

from dotenv import load_dotenv

# Load .env BEFORE any local imports that read env vars
load_dotenv(override=True)

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from audio_capture import AudioCapture, RecordingDisabled
from calendar_poller import poll_for_upcoming_meetings
from contact_repository import fetch_contacts as _fetch_contacts
from email_file_reader import parse_eml, parse_mbox
from entity_extractor import extract_entities, has_meaningful_extraction
from gmail_reader import fetch_recent_emails
from hydradb_client import generate_pre_call_brief, write_interaction_to_hydradb

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


async def push_error(message: str):
    await push_event({"type": "error", "message": message})


def _on_task_error(task: asyncio.Task) -> None:
    """Log and push exceptions from fire-and-forget background tasks."""
    exc = task.exception() if not task.cancelled() else None
    if exc:
        asyncio.create_task(push_error(f"Background task failed: {exc}"))


@app.post("/recording/start")
async def start_recording(body: dict[str, Any]):
    try:
        AudioCapture.check_available()
    except RecordingDisabled as exc:
        return {"status": "disabled", "reason": str(exc)}

    recording_session["active"] = True
    recording_session["contact"] = body
    recording_session["buffer"] = []

    async def on_text(text: str):
        recording_session["buffer"].append(text)
        await push_transcript(text)
        if len(recording_session["buffer"]) % 5 == 0:
            context_block = " ".join(recording_session["buffer"][-10:])
            task = asyncio.create_task(_extract_and_store(context_block))
            task.add_done_callback(_on_task_error)

    capture = AudioCapture(on_text)
    recording_session["capture"] = capture
    capture.start()
    await push_transcript("Recording started.")
    return {"status": "recording"}


async def _extract_and_store(text: str):
    contact = recording_session.get("contact")
    if not contact:
        return

    extracted = await extract_entities(text)
    if not has_meaningful_extraction(extracted):
        return

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
        task = asyncio.create_task(_extract_and_store(full_text))
        task.add_done_callback(_on_task_error)

    await push_transcript("Recording stopped. Processing final chunk.")
    return {"status": "stopped"}


@app.get("/contacts")
async def list_contacts():
    """Return stored contacts from HydraDB memory graph."""
    return await _fetch_contacts()


@app.get("/brief/{contact_email}")
async def get_brief(contact_email: str, contact_name: str, company: str):
    return await generate_pre_call_brief(contact_email, contact_name, company)


@app.post("/ingest/file")
async def ingest_file_endpoint(file: UploadFile = File(...)):
    """Ingest a .eml or .mbox file. No auth required."""
    filename = (file.filename or "").lower()
    if not (filename.endswith(".eml") or filename.endswith(".mbox")):
        raise HTTPException(status_code=400, detail="Only .eml and .mbox files are supported.")

    data = await file.read()
    if filename.endswith(".eml"):
        parsed = parse_eml(data)
        emails = [parsed] if parsed else []
    else:
        emails = parse_mbox(data)

    if not emails:
        return {"status": "no_emails", "count": 0}

    task = asyncio.create_task(_ingest_email_list(emails))
    task.add_done_callback(_on_task_error)
    return {"status": "ingestion started", "count": len(emails)}


async def _ingest_email_list(emails: list[dict[str, Any]]) -> None:
    sem = asyncio.Semaphore(5)

    async def process_one(email_item: dict[str, Any]) -> None:
        async with sem:
            contact = email_item.get("contact", {})
            extracted = await extract_entities(email_item.get("body", ""))
            if not has_meaningful_extraction(extracted):
                return
            await write_interaction_to_hydradb(
                contact_email=contact.get("email", ""),
                contact_name=contact.get("name", ""),
                company=contact.get("company", ""),
                extracted=extracted,
                interaction_type="email",
                raw_text=email_item.get("body", ""),
            )

    tasks = [asyncio.create_task(process_one(e)) for e in emails]
    for t in tasks:
        t.add_done_callback(_on_task_error)
    await asyncio.gather(*tasks, return_exceptions=True)
    await push_event({"type": "ingest_complete", "count": len(emails)})


@app.post("/ingest/emails")
async def ingest_emails_endpoint():
    task = asyncio.create_task(ingest_emails_background())
    task.add_done_callback(_on_task_error)
    return {"status": "ingestion started"}


async def ingest_emails_background():
    emails = fetch_recent_emails(days_back=90)
    sem = asyncio.Semaphore(5)

    async def process_one(email: dict[str, Any]) -> None:
        async with sem:
            contact = email.get("contact", {})
            extracted = await extract_entities(email.get("body", ""))
            if not has_meaningful_extraction(extracted):
                return
            await write_interaction_to_hydradb(
                contact_email=contact.get("email", "unknown@example.com"),
                contact_name=contact.get("name", "Unknown contact"),
                company=contact.get("company", "Unknown company"),
                extracted=extracted,
                interaction_type="email",
                raw_text=email.get("body", ""),
            )

    tasks = [asyncio.create_task(process_one(e)) for e in emails]
    for t in tasks:
        t.add_done_callback(_on_task_error)
    await asyncio.gather(*tasks, return_exceptions=True)
    await push_event({"type": "ingest_complete", "count": len(emails)})


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
