import asyncio
from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter

from audio_capture import AudioCapture, RecordingDisabled
from ingestion_pipeline import process_interaction
from ws_manager import ConnectionManager


@dataclass
class RecordingSession:
    active: bool = False
    buffer: list[str] = field(default_factory=list)
    contact: dict[str, Any] | None = None
    capture: Any | None = None


router = APIRouter()


def _on_task_error(clients: ConnectionManager, task: asyncio.Task) -> None:
    exc = task.exception() if not task.cancelled() else None
    if exc:
        asyncio.create_task(clients.broadcast({"type": "error", "message": f"Background task failed: {exc}"}))


def create_recording_routes(session: RecordingSession, clients: ConnectionManager) -> APIRouter:

    async def _push_transcript(text: str) -> None:
        await clients.broadcast({"type": "transcript", "text": text})

    @router.post("/recording/start")
    async def start_recording(body: dict[str, Any]):
        try:
            AudioCapture.check_available()
        except RecordingDisabled as exc:
            return {"status": "disabled", "reason": str(exc)}

        session.active = True
        session.contact = body
        session.buffer = []

        async def on_text(text: str):
            session.buffer.append(text)
            await _push_transcript(text)
            if len(session.buffer) % 5 == 0:
                contact = session.contact or {}
                task = asyncio.create_task(
                    process_interaction(
                        text=" ".join(session.buffer[-10:]),
                        contact_email=contact.get("contactEmail") or contact.get("contact_email"),
                        contact_name=contact.get("contactName") or contact.get("contact_name"),
                        company=contact.get("company"),
                        interaction_type="call",
                    )
                )
                task.add_done_callback(lambda t: _on_task_error(clients, t))

        session.capture = AudioCapture(on_text)
        session.capture.start()
        await _push_transcript("Recording started.")
        return {"status": "recording"}

    @router.post("/recording/stop")
    async def stop_recording():
        session.active = False
        if session.capture:
            session.capture.stop()
        if session.buffer and session.contact:
            contact = session.contact
            task = asyncio.create_task(
                process_interaction(
                    text=" ".join(session.buffer),
                    contact_email=contact.get("contactEmail") or contact.get("contact_email"),
                    contact_name=contact.get("contactName") or contact.get("contact_name"),
                    company=contact.get("company"),
                    interaction_type="call",
                )
            )
            task.add_done_callback(lambda t: _on_task_error(clients, t))
        await _push_transcript("Recording stopped. Processing final chunk.")
        return {"status": "stopped"}

    return router
