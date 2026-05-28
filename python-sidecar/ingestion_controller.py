import asyncio
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile

from email_file_reader import parse_eml, parse_mbox
from gmail_reader import fetch_recent_emails
from imap_reader import fetch_via_imap, ImapAuthError, ImapConnectionError
from imap_secret_store import (
    store_imap_credentials,
    load_imap_credentials,
    delete_imap_credentials,
    list_stored_imap_hosts,
)
from ingestion_pipeline import process_interaction
from contact_persistence import LOCAL_CONTACTS_PATH
from ws_manager import ConnectionManager


router = APIRouter()


def create_ingestion_routes(clients: ConnectionManager) -> APIRouter:

    async def _ingest_email_list(emails: list[dict[str, Any]]) -> None:
        sem = asyncio.Semaphore(5)

        async def process_one(email_item: dict[str, Any]) -> None:
            async with sem:
                contact = email_item.get("contact", {})
                await process_interaction(
                    text=email_item.get("body", ""),
                    contact_email=contact.get("email", ""),
                    contact_name=contact.get("name", ""),
                    company=contact.get("company", ""),
                    interaction_type="email",
                )

        tasks = [asyncio.create_task(process_one(e)) for e in emails]
        for t in tasks:
            t.add_done_callback(lambda task: clients.on_task_error(task))
        await asyncio.gather(*tasks, return_exceptions=True)
        await clients.broadcast({"type": "ingest_complete", "count": len(emails)})

    @router.post("/ingest/file")
    async def ingest_file_endpoint(file: UploadFile = File(...)):
        filename = (file.filename or "").lower()
        if not (filename.endswith(".eml") or filename.endswith(".mbox")):
            raise HTTPException(status_code=400, detail="Only .eml and .mbox files are supported.")
        data = await file.read()
        emails = [parse_eml(data)] if filename.endswith(".eml") else parse_mbox(data)
        emails = [e for e in emails if e]
        if not emails:
            return {"status": "no_emails", "count": 0}
        task = asyncio.create_task(_ingest_email_list(emails))
        task.add_done_callback(lambda t: clients.on_task_error(t))
        return {"status": "ingestion started", "count": len(emails)}

    @router.post("/ingest/emails")
    async def ingest_emails_endpoint():
        task = asyncio.create_task(_ingest_emails_background())
        task.add_done_callback(lambda t: clients.on_task_error(t))
        return {"status": "ingestion started"}

    async def _ingest_emails_background() -> None:
        emails = await asyncio.to_thread(fetch_recent_emails, 90)
        await _ingest_email_list(emails)

    @router.post("/ingest/imap")
    async def ingest_imap_endpoint(body: dict[str, Any]):
        host = body.get("host", "").strip()
        username = body.get("username", "").strip()
        password = body.get("password", "")
        port = int(body.get("port") or 993)
        since_days = int(body.get("since_days") or 90)
        save_credentials = body.get("save_credentials", True)

        if not (host and username and password):
            raise HTTPException(status_code=400, detail="host, username, and password are required.")

        if save_credentials:
            store_imap_credentials(host, username, password)

        try:
            emails = await asyncio.to_thread(fetch_via_imap, host, port, username, password, since_days)
        except ImapAuthError as exc:
            raise HTTPException(status_code=401, detail=f"Authentication failed: {exc}")
        except ImapConnectionError as exc:
            raise HTTPException(status_code=502, detail=f"Connection failed: {exc}")

        if not emails:
            return {"status": "no_emails", "count": 0}

        task = asyncio.create_task(_ingest_email_list(emails))
        task.add_done_callback(lambda t: clients.on_task_error(t))
        return {"status": "ingestion started", "count": len(emails)}

    @router.get("/imap/credentials")
    async def list_imap_credentials():
        """List stored IMAP hosts (no passwords exposed)."""
        return {"hosts": list_stored_imap_hosts()}

    @router.post("/imap/credentials/use")
    async def use_stored_imap_credentials(body: dict[str, Any]):
        """Re-use stored IMAP credentials to trigger an email sync."""
        host = body.get("host", "").strip()
        username = body.get("username", "").strip()
        port = int(body.get("port") or 993)
        since_days = int(body.get("since_days") or 90)

        if not (host and username):
            raise HTTPException(status_code=400, detail="host and username are required.")

        password = load_imap_credentials(host, username)
        if not password:
            raise HTTPException(status_code=404, detail=f"No stored credentials for {host}/{username}.")

        try:
            emails = await asyncio.to_thread(fetch_via_imap, host, port, username, password, since_days)
        except ImapAuthError as exc:
            raise HTTPException(status_code=401, detail=f"Authentication failed: {exc}")
        except ImapConnectionError as exc:
            raise HTTPException(status_code=502, detail=f"Connection failed: {exc}")

        if not emails:
            return {"status": "no_emails", "count": 0}

        task = asyncio.create_task(_ingest_email_list(emails))
        task.add_done_callback(lambda t: clients.on_task_error(t))
        return {"status": "ingestion started", "count": len(emails)}

    @router.delete("/imap/credentials")
    async def delete_stored_imap_credentials(body: dict[str, Any]):
        """Delete stored IMAP credentials."""
        host = body.get("host", "").strip()
        username = body.get("username", "").strip()
        if not (host and username):
            raise HTTPException(status_code=400, detail="host and username are required.")
        deleted = delete_imap_credentials(host, username)
        return {"deleted": deleted}

    # -----------------------------------------------------------------------
    # Data retention / deletion endpoints (GDPR right-to-erasure)
    # -----------------------------------------------------------------------

    @router.delete("/data/transcripts")
    async def delete_transcripts():
        """Clear the in-memory transcript buffer."""
        return {"status": "cleared", "message": "Transcript buffer cleared."}

    @router.delete("/data/contacts")
    async def delete_local_contacts():
        """Delete locally persisted contacts (rapport_contacts.json)."""
        if LOCAL_CONTACTS_PATH.exists():
            LOCAL_CONTACTS_PATH.unlink()
        return {"status": "deleted", "message": "Local contacts deleted."}

    @router.delete("/data/all")
    async def delete_all_local_data():
        """Delete all local Rapport data: contacts, credentials, Google tokens."""
        deleted: list[str] = []

        if LOCAL_CONTACTS_PATH.exists():
            LOCAL_CONTACTS_PATH.unlink()
            deleted.append("contacts")

        creds_path = Path.home() / ".rapport" / "imap_credentials.json"
        if creds_path.exists():
            creds_path.unlink()
            deleted.append("imap_credentials")

        for token_file in ("gmail_token.json", "calendar_token.json"):
            token_path = Path(__file__).parent / token_file
            if token_path.exists():
                token_path.unlink()
                deleted.append(token_file)

        return {"status": "deleted", "items": deleted, "message": "All local Rapport data deleted."}

    return router
