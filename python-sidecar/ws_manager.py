from contextlib import suppress
from typing import Any

from fastapi import WebSocket


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
