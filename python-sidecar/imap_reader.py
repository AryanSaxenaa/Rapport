import email
import email.utils
import imaplib
import ssl
from datetime import datetime, timedelta
from email import policy as email_policy
from typing import Any

from html_utils import strip_html


class ImapAuthError(Exception):
    pass


class ImapConnectionError(Exception):
    pass


def fetch_via_imap(
    host: str,
    port: int,
    username: str,
    password: str,
    since_days: int = 90,
) -> list[dict[str, Any]]:
    """Fetch emails via IMAP SSL and return them in the standard Email shape."""
    ctx = ssl.create_default_context()
    try:
        imap = imaplib.IMAP4_SSL(host, port, ssl_context=ctx)
    except OSError as exc:
        raise ImapConnectionError(f"Cannot connect to {host}:{port} — {exc}") from exc

    try:
        imap.login(username, password)
    except imaplib.IMAP4.error as exc:
        imap.logout()
        raise ImapAuthError(str(exc)) from exc

    try:
        imap.select("INBOX", readonly=True)
        since_date = (datetime.now() - timedelta(days=since_days)).strftime("%d-%b-%Y")
        _status, msg_nums = imap.search(None, f"SINCE {since_date}")
        nums = msg_nums[0].split() if msg_nums[0] else []

        results: list[dict[str, Any]] = []
        for num in nums:
            try:
                _s, data = imap.fetch(num, "(RFC822)")
                raw = data[0][1] if data and data[0] else None
                if not isinstance(raw, bytes):
                    continue
                msg = email.message_from_bytes(raw, policy=email_policy.default)
                parsed = _parse_message(msg)
                if parsed:
                    results.append(parsed)
            except Exception:
                continue
    finally:
        try:
            imap.close()
            imap.logout()
        except Exception:
            pass

    return results


def _parse_message(msg: Any) -> dict[str, Any] | None:
    subject = str(msg.get("subject") or "")
    from_addr = str(msg.get("from") or "")
    date_str = str(msg.get("date") or "")
    body = _extract_body(msg)
    if not body:
        return None

    name, addr = email.utils.parseaddr(from_addr)
    return {
        "subject": subject,
        "body": body,
        "date": date_str,
        "contact": {
            "email": addr.lower(),
            "name": name or addr.split("@")[0].replace(".", " ").title(),
            "company": _guess_company(addr),
        },
    }


def _extract_body(msg: Any) -> str:
    plain = ""
    html_body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain" and not plain:
                try:
                    plain = part.get_content()
                except Exception:
                    plain = part.get_payload(decode=True).decode("utf-8", errors="replace")
            elif ct == "text/html" and not html_body:
                try:
                    html_body = part.get_content()
                except Exception:
                    html_body = part.get_payload(decode=True).decode("utf-8", errors="replace")
    else:
        ct = msg.get_content_type()
        try:
            text = msg.get_content()
        except Exception:
            text = msg.get_payload(decode=True).decode("utf-8", errors="replace")
        if ct == "text/plain":
            plain = text
        elif ct == "text/html":
            html_body = text

    if plain.strip():
        return plain.strip()
    if html_body.strip():
        return strip_html(html_body)
    return ""


def _guess_company(addr: str) -> str:
    if "@" not in addr:
        return ""
    domain = addr.split("@")[-1].lower()
    public = {"gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com", "me.com"}
    if domain in public:
        return ""
    return domain.split(".")[0].replace("-", " ").title()
