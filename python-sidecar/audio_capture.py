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

SAMPLE_RATE = 16000
CHUNK_SECONDS = 5
CHUNK_SIZE = SAMPLE_RATE * CHUNK_SECONDS


def _list_input_devices() -> list[dict[str, Any]]:
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
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(audio.astype(np.int16).tobytes())
    return buf.getvalue()


class AudioCapture:
    """Real microphone capture using sounddevice, with OpenRouter Whisper transcription.

    Falls back to simulated transcript lines when no microphone is available
    so the app remains end-to-end runnable for development.
    """

    def __init__(self, on_text: Callable[[str], Awaitable[None]]):
        self.on_text = on_text
        self._task: asyncio.Task | None = None
        self._running = False
        self._buffer: list[np.ndarray] = []
        self._sample_count = 0
        self._simulate = False

    def start(self):
        self._running = True
        self._task = asyncio.create_task(self._capture_loop())

    def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None

    async def _capture_loop(self):
        if not _HAS_SOUNDDEVICE:
            self._simulate = True
            await self._simulate_transcript()
            return

        devices = _list_input_devices()
        if not devices:
            self._simulate = True
            await self._simulate_transcript()
            return

        device_info = sd.query_devices(kind="input")
        if device_info is None or device_info["max_input_channels"] < 1:
            self._simulate = True
            await self._simulate_transcript()
            return

        try:
            await self._real_capture()
        except Exception:
            self._simulate = True
            await self._simulate_transcript()

    async def _real_capture(self):
        device_info = sd.query_devices(kind="input")
        samplerate = int(device_info.get("default_samplerate", SAMPLE_RATE))

        q: asyncio.Queue[np.ndarray] = asyncio.Queue()

        def callback(indata: np.ndarray, _frames: int, _time_info, _status):
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

    async def _transcribe_and_push(self, wav_bytes: bytes):
        text = await transcribe_audio_chunk(wav_bytes)
        if text:
            await self.on_text(text)

    async def _simulate_transcript(self):
        lines = [
            "Mira is asking whether the audit export is available for regional admins.",
            "Priya wants a short written security summary before she approves rollout.",
            "Owen is holding budget until procurement confirms Q3 timing.",
            "Mira prefers a phased rollout with one named operations owner.",
            "The group agreed to review retention settings before Friday.",
        ]
        index = 0
        while self._running:
            await asyncio.sleep(4)
            await self.on_text(lines[index % len(lines)])
            index += 1
