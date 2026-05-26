"""Parse .eml and .mbox files into the same Email shape used by gmail_reader."""

import email
import email.policy
import mailbox
import re
from email.message import Message
from html.parser import HTMLParser
from io import BytesIO
from typing import Any


class _Tagger(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def get_text(self) -> str:
        return " ".join(self._parts)


def _strip_html(html_content: str) -> str:
    tagger = _Tagger()
    tagger.feed(html_content)
    text = tagger.get_text()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


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
        return _strip_html(html_body)[:8000]
    return ""


def _parse_message(msg: Message) -> dict[str, Any] | None:
    """Convert a stdlib Message into the canonical Email dict."""
    from_header = msg.get("From", "")
    to_header = msg.get("To", "")
    subject = msg.get("Subject", "")
    date_str = msg.get("Date", "")
    msg_id = msg.get("Message-ID", "")

    contact_name = ""
    contact_email = ""
    if "<" in from_header:
        contact_name = from_header.split("<")[0].strip().strip('"')
        contact_email = from_header.split("<")[1].rstrip(">").strip()
    else:
        contact_email = from_header.strip()

    body = _extract_body(msg)
    if not body:
        return None

    company = contact_email.split("@")[-1] if "@" in contact_email else ""

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
    """Parse an .mbox file. Returns list of canonical Email dicts."""
    buf = BytesIO(data)

    class _BytesMbox(mailbox.mbox):
        def __init__(self, buf: BytesIO):
            self._buf = buf
            self._toc: dict = {}
            self._next_key = 0
            self._pending: bool = False
            self._pending_sync: bool = False
            self._locked: bool = False
            self._file = buf
            self._file_length: int | None = None
            self._generate_toc()

    results: list[dict[str, Any]] = []
    raw_text = data.decode("utf-8", errors="replace")
    current: list[str] = []

    for line in raw_text.splitlines(keepends=True):
        if line.startswith("From ") and current:
            msg = email.message_from_string("".join(current), policy=email.policy.compat32)
            parsed = _parse_message(msg)
            if parsed:
                results.append(parsed)
            current = [line]
        else:
            current.append(line)

    if current:
        msg = email.message_from_string("".join(current), policy=email.policy.compat32)
        parsed = _parse_message(msg)
        if parsed:
            results.append(parsed)

    return results
