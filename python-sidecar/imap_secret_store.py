"""Encrypts IMAP credentials at rest using Fernet symmetric encryption.

The encryption key is derived from a machine-specific seed so passwords are
not stored in plaintext on disk.  The key is never written to disk itself.
"""

import base64
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet

_CREDENTIALS_PATH = Path.home() / ".rapport" / "imap_credentials.json"

_FERNET: Fernet | None = None


def _get_fernet() -> Fernet:
    """Return a Fernet instance seeded from the machine hostname + a fixed app salt."""
    global _FERNET  # noqa: PLW0603
    if _FERNET is not None:
        return _FERNET
    seed = f"rapport-imap-{os.environ.get('COMPUTERNAME', os.environ.get('HOSTNAME', 'default'))}".encode()
    key = hashlib.sha256(seed).digest()
    fernet_key = base64.urlsafe_b64encode(key)
    _FERNET = Fernet(fernet_key)
    return _FERNET


def _load_store() -> dict[str, Any]:
    if not _CREDENTIALS_PATH.exists():
        return {}
    try:
        return json.loads(_CREDENTIALS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_store(store: dict[str, Any]) -> None:
    _CREDENTIALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CREDENTIALS_PATH.write_text(json.dumps(store, indent=2), encoding="utf-8")


def store_imap_credentials(host: str, username: str, password: str) -> None:
    """Encrypt and persist IMAP credentials for a given host/username pair."""
    fernet = _get_fernet()
    encrypted = fernet.encrypt(password.encode("utf-8")).decode("utf-8")
    store = _load_store()
    key = f"{host}|{username}".lower()
    store[key] = {"host": host, "username": username, "password": encrypted}
    _save_store(store)


def load_imap_credentials(host: str, username: str) -> str | None:
    """Retrieve and decrypt the stored IMAP password, or None if not found."""
    store = _load_store()
    key = f"{host}|{username}".lower()
    entry = store.get(key)
    if not entry or not entry.get("password"):
        return None
    try:
        fernet = _get_fernet()
        return fernet.decrypt(entry["password"].encode("utf-8")).decode("utf-8")
    except Exception:
        return None


def delete_imap_credentials(host: str, username: str) -> bool:
    """Remove stored credentials. Returns True if something was deleted."""
    store = _load_store()
    key = f"{host}|{username}".lower()
    if key in store:
        del store[key]
        _save_store(store)
        return True
    return False


def list_stored_imap_hosts() -> list[str]:
    """Return unique hosts that have stored credentials."""
    store = _load_store()
    return sorted({entry.get("host", "") for entry in store.values() if entry.get("host")})
