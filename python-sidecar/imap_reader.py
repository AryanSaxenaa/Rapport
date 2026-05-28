import email
import imaplib
import ssl
from datetime import datetime, timedelta
from email import policy as email_policy
from email.message import Message as _EmailMessage
from html_utils import derive_company, parse_from_header, strip_html
from sidecar_types import EmailItem


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
) -> list[EmailItem]:
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

        results: list[EmailItem] = []
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
            except Exception as exc:
                print(f"IMAP: failed to parse message {num.decode() if isinstance(num, bytes) else num} — {exc}")
                continue
    finally:
        try:
            imap.close()
            imap.logout()
        except Exception:
            pass

    return results


def _parse_message(msg: _EmailMessage) -> EmailItem | None:
    subject = str(msg.get("subject") or "")
    from_addr = str(msg.get("from") or "")
    date_str = str(msg.get("date") or "")
    body = _extract_body(msg)
    if not body:
        return None

    name, addr = parse_from_header(from_addr)
    return {
        "subject": subject,
        "body": body,
        "date": date_str,
        "contact": {
            "email": addr,
            "name": name or addr.split("@")[0].replace(".", " ").title(),
            "company": derive_company(addr),
        },
    }


def _extract_body(msg: _EmailMessage) -> str:
    """Extract plain-text body from an email message."""
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

