from dataclasses import dataclass, field
from fastapi import APIRouter

from audio_capture import AudioCapture, RecordingDisabled
from contact_persistence import normalize_contact
from ingestion_pipeline import process_interaction
from sidecar_types import ContactDict
from ws_manager import ConnectionManager


@dataclass
class RecordingSession:
    active: bool = False
    buffer: list[str] = field(default_factory=list)
    contact: ContactDict | None = None
    capture: AudioCapture | None = None


router = APIRouter()


def create_recording_routes(session: RecordingSession, clients: ConnectionManager) -> APIRouter:

    async def _push_transcript(text: str) -> None:
        await clients.broadcast({"type": "transcript", "text": text})

    @router.post("/recording/start")
    async def start_recording(body: dict[str, str]):
        try:
            AudioCapture.check_available()
        except RecordingDisabled as exc:
            return {"status": "disabled", "reason": str(exc)}

        session.active = True
        session.contact = normalize_contact(body)
        session.buffer = []

        async def on_text(text: str):
            session.buffer.append(text)
            await _push_transcript(text)
            if len(session.buffer) % 5 == 0:
                contact = session.contact or {}
                error = await process_interaction(
                    text=" ".join(session.buffer[-10:]),
                    contact_email=contact.get("contactEmail"),
                    contact_name=contact.get("contactName"),
                    company=contact.get("company"),
                    interaction_type="call",
                )
                if error:
                    await clients.broadcast({"type": "error", "message": f"Extraction warning: {error}"})

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
            error = await process_interaction(
                text=" ".join(session.buffer),
                contact_email=contact.get("contactEmail"),
                contact_name=contact.get("contactName"),
                company=contact.get("company"),
                interaction_type="call",
            )
            if error:
                await clients.broadcast({"type": "error", "message": f"Extraction error: {error}"})
        await _push_transcript("Recording stopped. Processing final chunk.")
        return {"status": "stopped"}

    return router
