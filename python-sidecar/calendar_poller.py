import asyncio
import os
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from google_oauth import get_service
from html_utils import derive_company
from sidecar_types import MeetingInfo

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
POLL_INTERVAL_SECONDS = 60
UPCOMING_WINDOW_MINUTES = 30


def _get_calendar_service():
    return get_service("calendar", "v3", SCOPES, "calendar_token.json")


def _parse_attendee(attendee: dict[str, Any]) -> dict[str, str]:
    email = attendee.get("email", "")
    name = attendee.get("displayName", "") or (email.split("@")[0] if email else "Unknown")
    return {"name": name, "email": email}


async def poll_for_upcoming_meetings(
    on_upcoming_meeting: Callable[[MeetingInfo], Awaitable[None]],
):
    service = _get_calendar_service()
    if not service:
        print("Calendar: credentials.json not found — skipping calendar polling.")
        return

    seen_event_ids: set[str] = set()

    while True:
        try:
            now = datetime.now(timezone.utc)
            window_end = now + timedelta(minutes=UPCOMING_WINDOW_MINUTES)

            # googleapiclient uses synchronous HTTP — run in a thread.
            events_result = await asyncio.to_thread(
                service.events()
                .list(
                    calendarId="primary",
                    timeMin=now.isoformat(),
                    timeMax=window_end.isoformat(),
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute
            )

            for event in events_result.get("items", []):
                event_id = event.get("id", "")
                if event_id in seen_event_ids:
                    continue
                seen_event_ids.add(event_id)

                attendees = [_parse_attendee(a) for a in event.get("attendees", [])]
                my_email = os.getenv("MY_EMAIL", "").lower()
                target = next((a for a in attendees if a["email"].lower() != my_email), None)
                if not target:
                    continue

                await on_upcoming_meeting({
                    "event_id": event_id,
                    "summary": event.get("summary", "No title"),
                    "contact_email": target["email"],
                    "contact_name": target["name"],
                    "company": derive_company(target["email"]),
                    "start_time": event.get("start", {}).get("dateTime"),
                })

        except Exception as exc:
            print(f"Calendar: poll error: {exc}")

        await asyncio.sleep(POLL_INTERVAL_SECONDS)
