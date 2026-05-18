from typing import Any


def fetch_recent_emails(days_back: int = 90) -> list[dict[str, Any]]:
    """Return Gmail messages when OAuth credentials are configured.

    The production hook belongs here: credentials.json in this folder, token in
    ~/.rapport/gmail_token.json, Gmail readonly scope. Until configured, return
    an empty list so manual briefing and call capture keep working.
    """

    _ = days_back
    return []
