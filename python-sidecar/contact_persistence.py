import json
from pathlib import Path
from typing import Any

from sidecar_types import ContactDict

LOCAL_CONTACTS_PATH = Path(__file__).parent / "rapport_contacts.json"


def normalize_contact(contact: dict[str, Any]) -> ContactDict:
    email = (contact.get("contactEmail") or "").strip()
    name = (contact.get("contactName") or "").strip()
    company = (contact.get("company") or "").strip()
    return {
        "contactEmail": email,
        "contactName": name or (email.split("@")[0].replace(".", " ").title() if email else "Unknown contact"),
        "company": company,
        "stance": contact.get("stance") or "neutral",
        "lastInteraction": contact.get("lastInteraction") or contact.get("interaction_date") or "",
        "topics": contact.get("topics") or contact.get("topics_raised") or [],
        "sentimentShift": contact.get("sentiment_shift") or "",
        "commitments": contact.get("commitments") or [],
        "unresolved": contact.get("unresolved") or [],
        "summary": contact.get("summary") or "",
    }


def load_local_contacts() -> list[ContactDict]:
    if not LOCAL_CONTACTS_PATH.exists():
        return []
    try:
        raw = json.loads(LOCAL_CONTACTS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    contacts = raw if isinstance(raw, list) else raw.get("contacts", [])
    return [normalize_contact(c) for c in contacts if isinstance(c, dict)]


def save_local_contact(contact: dict[str, Any]) -> None:
    normalised = normalize_contact(contact)
    email = normalised.get("contactEmail", "")
    if not email:
        return

    contacts = load_local_contacts()
    by_email = {c.get("contactEmail", "").lower(): c for c in contacts}
    existing: ContactDict = by_email.get(email.lower(), {})  # type: ignore[assignment]
    by_email[email.lower()] = {**existing, **normalised}

    LOCAL_CONTACTS_PATH.write_text(
        json.dumps({"contacts": list(by_email.values())}, indent=2),
        encoding="utf-8",
    )

