"""Shared HTML → plain-text stripping using html.parser."""

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
    """Strip HTML tags, convert entities, and collapse whitespace."""
    tagger = _Tagger()
    tagger.feed(html_content)
    text = tagger.get_text()
    text = re.sub(r"\s+", " ", text)
    return text.strip()
