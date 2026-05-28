"""Run this script to authenticate Rapport with your Google Calendar.

A browser window will open. Log in with your Google account and grant
Calendar readonly access. The token is cached to ~/.rapport/calendar_token.json.
You only need to do this once — tokens auto-refresh thereafter.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from typing import Any

from google_oauth import get_service

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

print("Opening browser for Google Calendar OAuth...")

service: Any = get_service("calendar", "v3", SCOPES, "calendar_token.json", open_browser=True)
if not service:
    print("\n credentials.json not found or auth failed.")
    print("   Place credentials.json in python-sidecar/ (download from Google Cloud Console).")
    print("   Visit: https://console.cloud.google.com/apis/credentials")
    sys.exit(1)

try:
    calendar = service.calendars().get(calendarId="primary").execute()
    print(f"\n Authenticated with Calendar: {calendar.get('summary', 'Primary')}")
    print("   Token saved to ~/.rapport/calendar_token.json")
except Exception as exc:
    error_str = str(exc)
    if "has not been used" in error_str or "not enabled" in error_str or "403" in error_str:
        print("\n Calendar API is not enabled yet.")
        print("   Visit: https://console.cloud.google.com/apis/library/calendar-json.googleapis.com?project=rapport-496712")
        print("   Click ENABLE, wait a minute, then run this script again.")
    else:
        print(f"\n Calendar auth failed: {exc}")
