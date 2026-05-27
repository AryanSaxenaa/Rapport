import asyncio
import io
import os
import wave
from collections.abc import Awaitable, Callable
from typing import Any

import numpy as np

try:
    import sounddevice as sd
    _HAS_SOUNDDEVICE = True
except ImportError:
    _HAS_SOUNDDEVICE = False

from transcription import transcribe_audio_chunk
from sidecar_types import DeviceInfo

SAMPLE_RATE = 16000
CHUNK_SECONDS = 5
CHUNK_SIZE = SAMPLE_RATE * CHUNK_SECONDS


class RecordingDisabled(Exception):
    """Raised when recording cannot start due to a missing dependency."""
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _list_input_devices() -> list[DeviceInfo]:
    if not _HAS_SOUNDDEVICE:
        return []
    devices = sd.query_devices()
    return [
        {
            "index": d["index"],
            "name": d["name"],
            "channels": d["max_input_channels"],
            "default_samplerate": d["default_samplerate"],
        }
        for d in devices
        if d["max_input_channels"] > 0
    ]


def _numpy_to_wav_bytes(audio: np.ndarray, sample_rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio.astype(np.int16).tobytes())
    return buf.getvalue()


class AudioCapture:
    """Real microphone capture using sounddevice with OpenRouter Whisper transcription.

    Raises RecordingDisabled at start() if the mic or transcription API is unavailable.
    Never simulates or fabricates transcript content.
    """

    def __init__(self, on_text: Callable[[str], Awaitable[None]]):
        self.on_text = on_text
        self._task: asyncio.Task | None = None
        self._running = False
        self._buffer: list[np.ndarray] = []
        self._sample_count = 0

    @staticmethod
    def check_available() -> None:
        if not _HAS_SOUNDDEVICE:
            raise RecordingDisabled(
                "sounddevice not installed — run: pip install sounddevice"
            )
        devices = _list_input_devices()
        if not devices:
            raise RecordingDisabled(
                "No microphone found. Connect a mic and restart."
            )
        device_info = sd.query_devices(kind="input")
        if device_info is None or device_info["max_input_channels"] < 1:
            raise RecordingDisabled(
                "Default input device has no input channels. Check OS audio settings."
            )
        if not os.getenv("OPENROUTER_API_KEY"):
            raise RecordingDisabled(
                "OPENROUTER_API_KEY missing — transcription unavailable. Set it in .env."
            )

    def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._capture_loop())

    def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None

    async def _capture_loop(self) -> None:
        device_info = sd.query_devices(kind="input")
        samplerate = int(device_info.get("default_samplerate", SAMPLE_RATE))

        q: asyncio.Queue[np.ndarray] = asyncio.Queue()

        def callback(indata: np.ndarray, _frames: int, _time_info, _status) -> None:
            q.put_nowait(indata.copy())

        stream = sd.InputStream(
            samplerate=samplerate,
            channels=1,
            dtype="int16",
            callback=callback,
        )

        with stream:
            while self._running:
                try:
                    chunk = await asyncio.wait_for(q.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                self._buffer.append(chunk.flatten())
                self._sample_count += len(chunk)

                if self._sample_count >= samplerate * CHUNK_SECONDS:
                    audio = np.concatenate(self._buffer)
                    wav_bytes = _numpy_to_wav_bytes(audio, samplerate)
                    self._buffer = []
                    self._sample_count = 0
                    asyncio.create_task(self._transcribe_and_push(wav_bytes))

    async def _transcribe_and_push(self, wav_bytes: bytes) -> None:
        text = await transcribe_audio_chunk(wav_bytes)
        if text:
            await self.on_text(text)
