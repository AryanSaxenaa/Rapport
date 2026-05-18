import os
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
CREDENTIALS_PATH = Path(__file__).parent / "credentials.json"
TOKEN_DIR = Path.home() / ".rapport"
TOKEN_PATH = TOKEN_DIR / "gmail_token.json"


def _get_gmail_service():
    """Authenticate and return a Gmail API service, or None if not configured."""
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

    return build("gmail", "v1", credentials=creds)


def _parse_email_payload(payload: dict[str, Any]) -> str:
    """Extract plain-text body from a Gmail message payload."""
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        import base64
        data = payload["body"]["data"]
        return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

    if payload.get("parts"):
        for part in payload["parts"]:
            result = _parse_email_payload(part)
            if result:
                return result

    return ""


def _parse_email_message(msg: dict[str, Any]) -> dict[str, Any] | None:
    """Convert a Gmail API message into a simplified email dict."""
    headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
    body = _parse_email_payload(msg.get("payload", {}))

    if not body:
        return None

    from_header = headers.get("from", "")
    to_header = headers.get("to", "")
    subject = headers.get("subject", "")
    date_str = headers.get("date", "")

    # Extract name and email from "From" header: "Name <email>"
    contact_name = ""
    contact_email = ""
    if "<" in from_header:
        contact_name = from_header.split("<")[0].strip().strip('"')
        contact_email = from_header.split("<")[1].rstrip(">")
    else:
        contact_email = from_header.strip()

    company = contact_email.split("@")[-1] if "@" in contact_email else ""

    return {
        "id": msg.get("id"),
        "thread_id": msg.get("threadId"),
        "subject": subject,
        "from": from_header,
        "to": to_header,
        "date": date_str,
        "body": body[:8000],  # truncate to avoid memory blowup
        "contact": {
            "name": contact_name or contact_email.split("@")[0],
            "email": contact_email,
            "company": company,
        },
    }


def fetch_recent_emails(days_back: int = 90) -> list[dict[str, Any]]:
    """Fetch recent emails from Gmail via the API.

    Requires credentials.json in the python-sidecar directory.
    Returns an empty list with a logged warning if not configured.
    """
    service = _get_gmail_service()
    if not service:
        print("Gmail: credentials.json not found at", CREDENTIALS_PATH)
        print("Gmail: skipping email ingestion — place credentials.json in python-sidecar/")
        return []

    try:
        after_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y/%m/%d")
        results = (
            service.users()
            .messages()
            .list(userId="me", q=f"after:{after_date}", maxResults=50)
            .execute()
        )

        messages = results.get("messages", [])
        if not messages:
            return []

        emails = []
        for msg_meta in messages:
            msg = (
                service.users()
                .messages()
                .get(userId="me", id=msg_meta["id"], format="full")
                .execute()
            )
            parsed = _parse_email_message(msg)
            if parsed:
                emails.append(parsed)

        return emails

    except Exception as exc:
        print(f"Gmail: error fetching emails: {exc}")
        return []
