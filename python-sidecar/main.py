import asyncio
import os
from contextlib import suppress
from dataclasses import dataclass, field
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
from hydradb_client import (
    API_KEY as HYDRADB_API_KEY,
    generate_pre_call_brief,
    write_interaction_to_hydradb,
    _hydradb_client,
)
from imap_reader import fetch_via_imap, ImapAuthError, ImapConnectionError
from relationship_graph import build_graph, store_relations


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class ConnectionManager:
    def __init__(self) -> None:
        self._clients: list[WebSocket] = []

    def add(self, ws: WebSocket) -> None:
        self._clients.append(ws)

    def remove(self, ws: WebSocket) -> None:
        with suppress(ValueError):
            self._clients.remove(ws)

    async def broadcast(self, payload: dict[str, Any]) -> None:
        for ws in self._clients[:]:
            try:
                await ws.send_json(payload)
            except Exception:
                self.remove(ws)


@dataclass
class RecordingSession:
    active: bool = False
    buffer: list[str] = field(default_factory=list)
    contact: dict[str, Any] | None = None
    capture: Any | None = None


_clients = ConnectionManager()
_session = RecordingSession()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="Rapport Sidecar", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "online", "service": "rapport-sidecar"}


@app.get("/status")
async def get_status():
    """Return per-dependency availability for the settings panel."""
    mic_ok, mic_reason = _check_mic()
    return {
        "hydradb": {"ok": bool(HYDRADB_API_KEY), "reason": None if HYDRADB_API_KEY else "HYDRA_DB_API_KEY not set"},
        "openrouter": {"ok": bool(os.getenv("OPENROUTER_API_KEY")), "reason": None if os.getenv("OPENROUTER_API_KEY") else "OPENROUTER_API_KEY not set"},
        "microphone": {"ok": mic_ok, "reason": mic_reason},
        "imap": {"ok": True, "reason": "Provide host/credentials to sync"},
    }


def _check_mic() -> tuple[bool, str | None]:
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        has_input = any(d.get("max_input_channels", 0) > 0 for d in devices)
        return (True, None) if has_input else (False, "No input devices found")
    except Exception as exc:
        return False, str(exc)


@app.websocket("/ws/transcript")
async def transcript_ws(websocket: WebSocket):
    await websocket.accept()
    _clients.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        _clients.remove(websocket)


async def _push(payload: dict[str, Any]) -> None:
    await _clients.broadcast(payload)


async def _push_transcript(text: str) -> None:
    await _push({"type": "transcript", "text": text})


async def _push_error(message: str) -> None:
    await _push({"type": "error", "message": message})


def _on_task_error(task: asyncio.Task) -> None:
    exc = task.exception() if not task.cancelled() else None
    if exc:
        asyncio.create_task(_push_error(f"Background task failed: {exc}"))


# ---------------------------------------------------------------------------
# Recording
# ---------------------------------------------------------------------------

@app.post("/recording/start")
async def start_recording(body: dict[str, Any]):
    try:
        AudioCapture.check_available()
    except RecordingDisabled as exc:
        return {"status": "disabled", "reason": str(exc)}

    _session.active = True
    _session.contact = body
    _session.buffer = []

    async def on_text(text: str):
        _session.buffer.append(text)
        await _push_transcript(text)
        if len(_session.buffer) % 5 == 0:
            task = asyncio.create_task(_extract_and_store(" ".join(_session.buffer[-10:])))
            task.add_done_callback(_on_task_error)

    _session.capture = AudioCapture(on_text)
    _session.capture.start()
    await _push_transcript("Recording started.")
    return {"status": "recording"}


async def _extract_and_store(text: str) -> None:
    contact = _session.contact
    if not contact:
        return
    extracted = await extract_entities(text)
    if not has_meaningful_extraction(extracted):
        return
    contact_email = contact.get("contactEmail") or contact.get("contact_email")
    await write_interaction_to_hydradb(
        contact_email=contact_email,
        contact_name=contact.get("contactName") or contact.get("contact_name"),
        company=contact.get("company"),
        extracted=extracted,
        interaction_type="call",
        raw_text=text,
    )
    client = _hydradb_client()
    if client:
        with suppress(Exception):
            await store_relations(client, extracted.get("relations") or [], contact_email)


@app.post("/recording/stop")
async def stop_recording():
    _session.active = False
    if _session.capture:
        _session.capture.stop()
    if _session.buffer and _session.contact:
        task = asyncio.create_task(_extract_and_store(" ".join(_session.buffer)))
        task.add_done_callback(_on_task_error)
    await _push_transcript("Recording stopped. Processing final chunk.")
    return {"status": "stopped"}


# ---------------------------------------------------------------------------
# Contacts / Graph / Brief
# ---------------------------------------------------------------------------

@app.get("/contacts")
async def list_contacts():
    return await _fetch_contacts()


@app.get("/graph")
async def get_graph():
    return await build_graph()


@app.get("/brief/{contact_email}")
async def get_brief(contact_email: str, contact_name: str, company: str):
    return await generate_pre_call_brief(contact_email, contact_name, company)


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------

@app.post("/ingest/file")
async def ingest_file_endpoint(file: UploadFile = File(...)):
    filename = (file.filename or "").lower()
    if not (filename.endswith(".eml") or filename.endswith(".mbox")):
        raise HTTPException(status_code=400, detail="Only .eml and .mbox files are supported.")
    data = await file.read()
    emails = [parse_eml(data)] if filename.endswith(".eml") else parse_mbox(data)
    emails = [e for e in emails if e]
    if not emails:
        return {"status": "no_emails", "count": 0}
    task = asyncio.create_task(_ingest_email_list(emails))
    task.add_done_callback(_on_task_error)
    return {"status": "ingestion started", "count": len(emails)}


@app.post("/ingest/emails")
async def ingest_emails_endpoint():
    task = asyncio.create_task(_ingest_emails_background())
    task.add_done_callback(_on_task_error)
    return {"status": "ingestion started"}


@app.post("/ingest/imap")
async def ingest_imap_endpoint(body: dict[str, Any]):
    host = body.get("host", "").strip()
    username = body.get("username", "").strip()
    password = body.get("password", "")
    port = int(body.get("port") or 993)
    since_days = int(body.get("since_days") or 90)

    if not (host and username and password):
        raise HTTPException(status_code=400, detail="host, username, and password are required.")

    try:
        emails = await asyncio.to_thread(fetch_via_imap, host, port, username, password, since_days)
    except ImapAuthError as exc:
        raise HTTPException(status_code=401, detail=f"Authentication failed: {exc}")
    except ImapConnectionError as exc:
        raise HTTPException(status_code=502, detail=f"Connection failed: {exc}")

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
            contact_email = contact.get("email", "")
            await write_interaction_to_hydradb(
                contact_email=contact_email,
                contact_name=contact.get("name", ""),
                company=contact.get("company", ""),
                extracted=extracted,
                interaction_type="email",
                raw_text=email_item.get("body", ""),
            )
            client = _hydradb_client()
            if client:
                with suppress(Exception):
                    await store_relations(client, extracted.get("relations") or [], contact_email)

    tasks = [asyncio.create_task(process_one(e)) for e in emails]
    for t in tasks:
        t.add_done_callback(_on_task_error)
    await asyncio.gather(*tasks, return_exceptions=True)
    await _push({"type": "ingest_complete", "count": len(emails)})


async def _ingest_emails_background() -> None:
    emails = fetch_recent_emails(days_back=90)
    await _ingest_email_list(emails)


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup():
    async def on_upcoming_meeting(meeting_info: dict[str, Any]):
        brief = await generate_pre_call_brief(
            contact_email=meeting_info["contact_email"],
            contact_name=meeting_info["contact_name"],
            company=meeting_info["company"],
        )
        await _push({"type": "brief", "data": {**brief, "trigger": "calendar"}})

    asyncio.create_task(poll_for_upcoming_meetings(on_upcoming_meeting))
