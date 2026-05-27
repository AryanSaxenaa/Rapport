"""Shared utilities: HTML stripping, email address parsing."""

import email.utils
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
    """Return (contact_name, contact_email) from an email From header.

    BUG-7 fix: the previous implementation split on '<' which fails for
    display names that themselves contain '<' (e.g. ``"Alice <Bob>" <a@b.com>``).
    ``email.utils.parseaddr`` handles all RFC 5322 edge cases correctly and is
    already used by ``imap_reader.py`` — this makes both ingestion paths
    consistent.
    """
    name, addr = email.utils.parseaddr(from_header)
    return name.strip().strip('"'), addr.lower().strip()


def derive_company(contact_email: str) -> str:
    """Return company domain from an email address, or empty string."""
    return contact_email.split("@")[-1] if "@" in contact_email else ""


def derive_name(contact_email: str, fallback: str = "") -> str:
    """Return a display name derived from the email local part, or fallback."""
    if not contact_email:
        return fallback
    return contact_email.split("@")[0]
