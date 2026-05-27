"""Parse .eml and .mbox files into the same Email shape used by gmail_reader."""

import email
import email.policy
from email.message import Message
from typing import Any

from html_utils import derive_company, parse_from_header, strip_html


def _extract_body(msg: Message) -> str:
    """Extract plain-text body from a Message. Falls back to stripped HTML."""
    plain: str = ""
    html_body: str = ""

    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            cd = str(part.get("Content-Disposition", ""))
            if "attachment" in cd:
                continue
            charset = part.get_content_charset() or "utf-8"
            payload = part.get_payload(decode=True)
            if not payload:
                continue
            text = payload.decode(charset, errors="replace")
            if ct == "text/plain" and not plain:
                plain = text
            elif ct == "text/html" and not html_body:
                html_body = text
    else:
        ct = msg.get_content_type()
        charset = msg.get_content_charset() or "utf-8"
        payload = msg.get_payload(decode=True)
        if payload:
            text = payload.decode(charset, errors="replace")
            if ct == "text/plain":
                plain = text
            elif ct == "text/html":
                html_body = text

    if plain:
        return plain[:8000]
    if html_body:
        return strip_html(html_body)[:8000]
    return ""


def _parse_message(msg: Message) -> dict[str, Any] | None:
    """Convert a stdlib Message into the canonical Email dict."""
    from_header = msg.get("From", "")
    to_header = msg.get("To", "")
    subject = msg.get("Subject", "")
    date_str = msg.get("Date", "")
    msg_id = msg.get("Message-ID", "")

    contact_name, contact_email = parse_from_header(from_header)

    body = _extract_body(msg)
    if not body:
        return None

    company = derive_company(contact_email)

    return {
        "id": msg_id,
        "thread_id": msg.get("Thread-Index", ""),
        "subject": subject,
        "from": from_header,
        "to": to_header,
        "date": date_str,
        "body": body,
        "contact": {
            "name": contact_name or (contact_email.split("@")[0] if contact_email else "Unknown"),
            "email": contact_email,
            "company": company,
        },
    }


def parse_eml(data: bytes) -> dict[str, Any] | None:
    """Parse a single .eml file. Returns canonical Email dict or None."""
    msg = email.message_from_bytes(data, policy=email.policy.compat32)
    return _parse_message(msg)


def parse_mbox(data: bytes) -> list[dict[str, Any]]:
    """Parse an .mbox file. Returns list of canonical Email dicts.

    Each message in mbox format is preceded by a ``From `` separator line.
    BUG-14 fix: that separator line must be *discarded*, not prepended to the
    next message body.  The previous code used ``current = [line]`` which
    included the ``From `` line in every message.
    """
    results: list[dict[str, Any]] = []
    raw_text = data.decode("utf-8", errors="replace")
    current: list[str] = []

    for line in raw_text.splitlines(keepends=True):
        if line.startswith("From "):
            if current:
                msg = email.message_from_string("".join(current), policy=email.policy.compat32)
                parsed = _parse_message(msg)
                if parsed:
                    results.append(parsed)
            current = []  # discard the separator line itself
        else:
            current.append(line)

    if current:
        msg = email.message_from_string("".join(current), policy=email.policy.compat32)
        parsed = _parse_message(msg)
        if parsed:
            results.append(parsed)

    return results
