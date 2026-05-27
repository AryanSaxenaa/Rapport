import asyncio
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile

from email_file_reader import parse_eml, parse_mbox
from gmail_reader import fetch_recent_emails
from imap_reader import fetch_via_imap, ImapAuthError, ImapConnectionError
from ingestion_pipeline import process_interaction
from ws_manager import ConnectionManager


router = APIRouter()


def _on_task_error(clients: ConnectionManager, task: asyncio.Task) -> None:
    exc = task.exception() if not task.cancelled() else None
    if exc:
        asyncio.create_task(clients.broadcast({"type": "error", "message": f"Background task failed: {exc}"}))


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
            t.add_done_callback(lambda task: _on_task_error(clients, task))
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
        task.add_done_callback(lambda t: _on_task_error(clients, t))
        return {"status": "ingestion started", "count": len(emails)}

    @router.post("/ingest/emails")
    async def ingest_emails_endpoint():
        task = asyncio.create_task(_ingest_emails_background())
        task.add_done_callback(lambda t: _on_task_error(clients, t))
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

        if not (host and username and password):
            raise HTTPException(status_code=400, detail="host, username, and password are required.")

        try:
            emails = await asyncio.to_thread(fetch_via_imap, host, port, username, password, since_days)
        except ImapAuthError as exc:
            raise HTTPException(status_code=401, detail=f"Authentication failed: {exc}")
        except ImapConnectionError as exc:
            raise HTTPException(status_code=502, detail=f"Connection failed: {exc}")

        if not emails:
            return {"status": "no_emails", "count": 0}

        task = asyncio.create_task(_ingest_email_list(emails))
        task.add_done_callback(lambda t: _on_task_error(clients, t))
        return {"status": "ingestion started", "count": len(emails)}

    return router
