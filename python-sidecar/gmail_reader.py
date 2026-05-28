import base64
from datetime import datetime, timedelta, timezone
from typing import Any

from google_oauth import get_service
from html_utils import derive_company, parse_from_header, strip_html
from sidecar_types import EmailItem

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def _get_gmail_service():
    return get_service("gmail", "v1", SCOPES, "gmail_token.json")


def _parse_email_payload(payload: dict[str, Any]) -> str:
    """Extract plain-text body. Falls back to stripped HTML for HTML-only emails."""
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")

    if payload.get("mimeType") == "text/html" and payload.get("body", {}).get("data"):
        html_content = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
        return strip_html(html_content)

    if payload.get("parts"):
        plain = ""
        html_fallback = ""
        for part in payload["parts"]:
            result = _parse_email_payload(part)
            if result and not plain and part.get("mimeType") == "text/plain":
                plain = result
            elif result and not html_fallback:
                html_fallback = result
        return plain or html_fallback

    return ""


def _parse_email_message(msg: dict[str, Any]) -> EmailItem | None:
    headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
    body = _parse_email_payload(msg.get("payload", {}))
    if not body:
        return None

    from_header = headers.get("from", "")
    contact_name, contact_email = parse_from_header(from_header)
    company = derive_company(contact_email)

    return {
        "id": msg.get("id"),
        "thread_id": msg.get("threadId"),
        "subject": headers.get("subject", ""),
        "from": from_header,
        "to": headers.get("to", ""),
        "date": headers.get("date", ""),
        "body": body[:8000],
        "contact": {
            "name": contact_name or contact_email.split("@")[0],
            "email": contact_email,
            "company": company,
        },
    }


def fetch_recent_emails(days_back: int = 90) -> list[EmailItem]:
    service = _get_gmail_service()
    if not service:
        print("Gmail: credentials.json not found — skipping OAuth email ingest.")
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
        emails = []
        for meta in messages:
            msg = service.users().messages().get(userId="me", id=meta["id"], format="full").execute()
            parsed = _parse_email_message(msg)
            if parsed:
                emails.append(parsed)
        return emails
    except Exception as exc:
        print(f"Gmail: error fetching emails: {exc}")
        return []
