"""Shared Google OAuth helper for Gmail and Calendar."""

from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

CREDENTIALS_PATH = Path(__file__).parent / "credentials.json"
TOKEN_DIR = Path.home() / ".rapport"


def get_service(api: str, version: str, scopes: list[str], token_filename: str) -> Any | None:
    """Authenticate and return a Google API service, or None if not configured.

    Returns a googleapiclient.discovery.Resource (not typed for compatibility with
    the library's dynamic method dispatch).
    """
    if not CREDENTIALS_PATH.exists():
        return None

    token_path = TOKEN_DIR / token_filename
    creds: Credentials | None = None

    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), scopes)
        except Exception:
            creds = None

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception:
            creds = None

    if not creds:
        try:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), scopes)
            creds = flow.run_local_server(port=0, open_browser=False)
        except Exception:
            return None

    TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json())  # type: ignore[union-attr]   # guaranteed non-None after auth flow above

    return build(api, version, credentials=creds)
