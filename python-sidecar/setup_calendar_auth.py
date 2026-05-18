"""Run this script to authenticate Rapport with your Google Calendar.

A browser window will open. Log in with your Google account and grant
Calendar readonly access. The token is cached to ~/.rapport/calendar_token.json.
You only need to do this once — tokens auto-refresh thereafter.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
CREDENTIALS_PATH = Path(__file__).parent / "credentials.json"
TOKEN_DIR = Path.home() / ".rapport"
TOKEN_PATH = TOKEN_DIR / "calendar_token.json"

print("Opening browser for Google Calendar OAuth...")

creds = None
if TOKEN_PATH.exists():
    try:
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    except Exception:
        creds = None

if creds and creds.expired and creds.refresh_token:
    creds.refresh(Request())

if not creds:
    if not CREDENTIALS_PATH.exists():
        print(f"credentials.json not found at {CREDENTIALS_PATH}")
        sys.exit(1)
    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
    creds = flow.run_local_server(port=0)

TOKEN_DIR.mkdir(parents=True, exist_ok=True)
with open(TOKEN_PATH, "w") as f:
    f.write(creds.to_json())

try:
    service = build("calendar", "v3", credentials=creds)
    calendar = service.calendars().get(calendarId="primary").execute()
    print(f"\n✅ Authenticated with Calendar: {calendar.get('summary', 'Primary')}")
    print(f"   Token saved to {TOKEN_PATH}")
except Exception as exc:
    error_str = str(exc)
    if "has not been used" in error_str or "not enabled" in error_str or "403" in error_str:
        print("\n❌ Calendar API is not enabled yet.")
        print("   Visit: https://console.cloud.google.com/apis/library/calendar-json.googleapis.com?project=rapport-496712")
        print("   Click ENABLE, wait a minute, then run this script again.")
    else:
        print(f"\n❌ Calendar auth failed: {exc}")
