import asyncio
from contextlib import suppress
from fastapi import WebSocket

from sidecar_types import WSMessage


class ConnectionManager:
    def __init__(self) -> None:
        self._clients: list[WebSocket] = []

    def add(self, ws: WebSocket) -> None:
        self._clients.append(ws)

    def remove(self, ws: WebSocket) -> None:
        with suppress(ValueError):
            self._clients.remove(ws)

    async def broadcast(self, payload: WSMessage) -> None:
        for ws in self._clients[:]:
            try:
                await ws.send_json(payload)
            except Exception:
                self.remove(ws)

    def on_task_error(self, task: asyncio.Task) -> None:
        """Propagate background-task failures to connected clients.

        The broadcast is fire-and-forget, but we always log to stderr so
        failures are visible even if all clients have disconnected.  The
        broadcast task itself is also chained to a callback so its errors
        are never silently swallowed.
        """
        if task.cancelled():
            return
        exc = task.exception()
        if not exc:
            return
        print(f"Background task failed: {exc}")
        broadcast_task = asyncio.create_task(
            self.broadcast({"type": "error", "message": f"Background task failed: {exc}"})
        )
        broadcast_task.add_done_callback(
            lambda t: (
                print(f"WS broadcast error: {t.exception()}")
                if not t.cancelled() and t.exception()
                else None
            )
        )
