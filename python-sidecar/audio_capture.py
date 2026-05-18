import asyncio
from collections.abc import Awaitable, Callable


class AudioCapture:
    """Development capture shim.

    Real system audio capture is platform-specific. This class keeps the app
    end-to-end runnable now and provides the same callback contract for a WASAPI
    or ScreenCaptureKit implementation later.
    """

    def __init__(self, on_text: Callable[[str], Awaitable[None]]):
        self.on_text = on_text
        self._task: asyncio.Task | None = None
        self._running = False

    def start(self):
        self._running = True
        self._task = asyncio.create_task(self._simulate_transcript())

    def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()

    async def _simulate_transcript(self):
        lines = [
            "Mira is asking whether the audit export is available for regional admins.",
            "Priya wants a short written security summary before she approves rollout.",
            "Owen is holding budget until procurement confirms Q3 timing.",
            "Mira prefers a phased rollout with one named operations owner.",
            "The group agreed to review retention settings before Friday."
        ]
        index = 0
        while self._running:
            await asyncio.sleep(4)
            await self.on_text(lines[index % len(lines)])
            index += 1
