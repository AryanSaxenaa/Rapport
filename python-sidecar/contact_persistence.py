import json
from datetime import date
from pathlib import Path
from typing import Any

LOCAL_CONTACTS_PATH = Path(__file__).parent / "rapport_contacts.json"


def normalize_contact(contact: dict[str, Any]) -> dict[str, Any]:
    email = (contact.get("contactEmail") or contact.get("contact_email") or "").strip()
    name = (contact.get("contactName") or contact.get("contact_name") or "").strip()
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


def load_local_contacts() -> list[dict[str, Any]]:
    if not LOCAL_CONTACTS_PATH.exists():
        return []
    try:
        raw = json.loads(LOCAL_CONTACTS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    contacts = raw if isinstance(raw, list) else raw.get("contacts", [])
    return [normalize_contact(c) for c in contacts if isinstance(c, dict)]


def save_local_contact(contact: dict[str, Any]) -> None:
    normalised = normalize_contact(contact)
    if not normalised["contactEmail"]:
        return

    contacts = load_local_contacts()
    by_email = {c["contactEmail"].lower(): c for c in contacts}
    existing = by_email.get(normalised["contactEmail"].lower(), {})
    by_email[normalised["contactEmail"].lower()] = {**existing, **normalised}

    LOCAL_CONTACTS_PATH.write_text(
        json.dumps({"contacts": list(by_email.values())}, indent=2),
        encoding="utf-8",
    )


def demo_contacts() -> list[dict[str, Any]]:
    return [
        {
            "contactEmail": "mira.voss@northstar-ledger.example",
            "contactName": "Mira Voss",
            "company": "Northstar Ledger",
            "stance": "skeptic",
            "lastInteraction": date.today().isoformat(),
            "topics": ["security review", "rollout workload", "budget timing"],
        },
        {
            "contactEmail": "jon.bell@apexfoundry.example",
            "contactName": "Jon Bell",
            "company": "Apex Foundry",
            "stance": "champion",
            "lastInteraction": date.today().isoformat(),
            "topics": ["pilot scope", "executive sponsor"],
        },
    ]
