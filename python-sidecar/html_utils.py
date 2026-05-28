"""Shared utilities: HTML stripping, email address parsing, LLM response cleaning."""

import email.utils
import re
from html.parser import HTMLParser

# Matches leading ```json / ``` fences that LLMs add around JSON responses.
_FENCE_RE = re.compile(r"^```[a-z]*\n?", re.MULTILINE)


def strip_json_fences(text: str) -> str:
    """Remove markdown code fences that LLMs commonly wrap JSON responses in."""
    text = _FENCE_RE.sub("", text.strip())
    return text.rstrip("`").strip()


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
    Uses ``email.utils.parseaddr`` for RFC 5322 compliance (handles display
    names containing '<', unlike naive split-on-'<').
    """
    name, addr = email.utils.parseaddr(from_header)
    return name.strip().strip('"'), addr.lower().strip()


def derive_company(contact_email: str) -> str:
    """Return company domain from an email address, or empty string."""
    return contact_email.split("@")[-1] if "@" in contact_email else ""

