import asyncio
from collections.abc import Awaitable, Callable
from typing import Any


async def poll_for_upcoming_meetings(on_upcoming_meeting: Callable[[dict[str, Any]], Awaitable[None]]):
    """Calendar watcher placeholder.

    Google Calendar OAuth can be added without touching the UI contract: call
    on_upcoming_meeting five minutes before a meeting with contact details.
    """

    _ = on_upcoming_meeting
    while True:
        await asyncio.sleep(60)
