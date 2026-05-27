import asyncio
import os
from pathlib import Path
from typing import Any

from dotenv import dotenv_values, load_dotenv

load_dotenv(override=True)

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from brief_generator import generate_pre_call_brief
from calendar_poller import poll_for_upcoming_meetings
from contact_repository import fetch_contacts as _fetch_contacts
from hydradb_client import API_KEY as HYDRADB_API_KEY
from ingestion_controller import create_ingestion_routes
from recording_controller import RecordingSession, create_recording_routes
from relationship_graph import build_graph
from sidecar_types import MeetingInfo
from ws_manager import ConnectionManager


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

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

app.include_router(create_recording_routes(_session, _clients))
app.include_router(create_ingestion_routes(_clients))


@app.get("/health")
async def health():
    return {"status": "online", "service": "rapport-sidecar"}


@app.get("/status")
async def get_status():
    mic_ok, mic_reason = _check_mic()
    return {
        "hydradb": {"ok": bool(HYDRADB_API_KEY), "reason": None if HYDRADB_API_KEY else "HYDRA_DB_API_KEY not set"},
        "openrouter": {"ok": bool(os.getenv("OPENROUTER_API_KEY")), "reason": None if os.getenv("OPENROUTER_API_KEY") else "OPENROUTER_API_KEY not set"},
        "microphone": {"ok": mic_ok, "reason": mic_reason},
        "imap": {"ok": True, "reason": "Provide host/credentials to sync"},
    }


@app.post("/configure")
async def configure(body: dict[str, Any]):
    env_path = Path(__file__).parent / ".env"
    allowed_keys = {"HYDRA_DB_API_KEY", "HYDRA_DB_TENANT_ID", "OPENROUTER_API_KEY"}
    updates = {k: v for k, v in body.items() if k in allowed_keys and v}
    if not updates:
        return {"status": "no_changes"}

    existing: dict[str, str | None] = dotenv_values(env_path) if env_path.exists() else {}
    existing.update(updates)
    entries = {k: v for k, v in existing.items() if v is not None}
    env_path.write_text(
        "\n".join(f"{k}={v}" for k, v in entries.items()) + "\n",
        encoding="utf-8",
    )
    load_dotenv(env_path, override=True)
    return {"status": "saved", "keys": list(updates.keys())}


@app.websocket("/ws/transcript")
async def transcript_ws(websocket: WebSocket):
    await websocket.accept()
    _clients.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        _clients.remove(websocket)


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
# Helpers
# ---------------------------------------------------------------------------

def _check_mic() -> tuple[bool, str | None]:
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        has_input = any(d.get("max_input_channels", 0) > 0 for d in devices)
        return (True, None) if has_input else (False, "No input devices found")
    except ImportError:
        return False, "sounddevice not installed — run: pip install sounddevice"
    except Exception as exc:
        return False, str(exc)


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup():
    async def on_upcoming_meeting(meeting_info: MeetingInfo):
        brief = await generate_pre_call_brief(
            contact_email=meeting_info.get("contact_email", ""),
            contact_name=meeting_info.get("contact_name", ""),
            company=meeting_info.get("company", ""),
        )
        await _clients.broadcast({"type": "brief", "data": {**brief, "trigger": "calendar"}})

    asyncio.create_task(poll_for_upcoming_meetings(on_upcoming_meeting))
