"""Shared utilities: HTML stripping, email address parsing."""

import re
from html.parser import HTMLParser


class _Tagger(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def get_text(self) -> str:
        return " ".join(self._parts)


def strip_html(html_content: str) -> str:
    tagger = _Tagger()
    tagger.feed(html_content)
    text = tagger.get_text()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_from_header(from_header: str) -> tuple[str, str]:
    """Return (contact_name, contact_email) from an email From header."""
    contact_name = ""
    contact_email = ""
    if "<" in from_header:
        contact_name = from_header.split("<")[0].strip().strip('"')
        contact_email = from_header.split("<")[1].rstrip(">").strip()
    else:
        contact_email = from_header.strip()
    return contact_name, contact_email


def derive_company(contact_email: str) -> str:
    """Return company domain from an email address, or empty string."""
    return contact_email.split("@")[-1] if "@" in contact_email else ""


def derive_name(contact_email: str, fallback: str = "") -> str:
    """Return a display name derived from the email local part, or fallback."""
    if not contact_email:
        return fallback
    return contact_email.split("@")[0]
