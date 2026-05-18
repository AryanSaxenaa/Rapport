import asyncio
import os
import json
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
CREDENTIALS_PATH = Path(__file__).parent / "credentials.json"
TOKEN_DIR = Path.home() / ".rapport"
TOKEN_PATH = TOKEN_DIR / "calendar_token.json"
POLL_INTERVAL_SECONDS = 60
UPCOMING_WINDOW_MINUTES = 30


def _get_calendar_service():
    """Authenticate and return a Calendar API service, or None if not configured."""
    if not CREDENTIALS_PATH.exists():
        return None

    creds = None
    if TOKEN_PATH.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
        except Exception:
            creds = None

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception:
            creds = None

    if not creds:
        try:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=0, open_browser=False)
        except Exception:
            return None

    TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    with open(TOKEN_PATH, "w") as f:
        f.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)


def _parse_attendee(attendee: dict[str, Any]) -> dict[str, str]:
    email = attendee.get("email", "")
    name = attendee.get("displayName", "")
    if not name:
        name = email.split("@")[0] if email else "Unknown"
    return {"name": name, "email": email}


async def poll_for_upcoming_meetings(
    on_upcoming_meeting: Callable[[dict[str, Any]], Awaitable[None]],
):
    """Poll Google Calendar for meetings starting within the next window.

    Fires the callback for each new upcoming meeting with contact details.
    Falls back to a no-op sleep loop when Calendar API is not configured.
    """
    service = _get_calendar_service()
    if not service:
        print("Calendar: credentials.json not found at", CREDENTIALS_PATH)
        print("Calendar: skipping — place credentials.json in python-sidecar/")
        _idle_loop()
        return

    seen_event_ids: set[str] = set()

    while True:
        try:
            now = datetime.now(timezone.utc)
            window_end = now + timedelta(minutes=UPCOMING_WINDOW_MINUTES)

            events_result = (
                service.events()
                .list(
                    calendarId="primary",
                    timeMin=now.isoformat(),
                    timeMax=window_end.isoformat(),
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )

            for event in events_result.get("items", []):
                event_id = event.get("id", "")
                if event_id in seen_event_ids:
                    continue
                seen_event_ids.add(event_id)

                attendees = [_parse_attendee(a) for a in event.get("attendees", [])]
                # Filter out self and pick the first external attendee
                my_email = os.getenv("MY_EMAIL", "").lower()
                target = next(
                    (a for a in attendees if a["email"].lower() != my_email),
                    None,
                )
                if not target:
                    continue

                meeting_info = {
                    "event_id": event_id,
                    "summary": event.get("summary", "No title"),
                    "contact_email": target["email"],
                    "contact_name": target["name"],
                    "company": target["email"].split("@")[-1] if "@" in target["email"] else "",
                    "start_time": event.get("start", {}).get("dateTime"),
                }

                await on_upcoming_meeting(meeting_info)

        except Exception as exc:
            print(f"Calendar: poll error: {exc}")

        await asyncio.sleep(POLL_INTERVAL_SECONDS)


async def _idle_loop():
    while True:
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
