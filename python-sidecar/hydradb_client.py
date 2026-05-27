import asyncio
import os
from collections.abc import Awaitable, Callable
from datetime import date
from typing import Any, TypeVar, overload

from hydra_db import AsyncHydraDB
from hydra_db.core import ApiError

from contact_persistence import normalize_contact, save_local_contact
from sidecar_types import ErrorPayload, ExtractionResult, ContactDict

T = TypeVar("T")

TENANT_ID = os.getenv("HYDRA_DB_TENANT_ID") or os.getenv("HYDRADB_TENANT_ID") or "orb"
API_KEY = os.getenv("HYDRA_DB_API_KEY")
RETRYABLE_STATUS_CODES = {429, 500, 503}


def _sub_tenant_id(contact_email: str | None) -> str:
    value = contact_email or "unknown"
    return value.replace("@", "_at_").replace(".", "_")


def _hydradb_client() -> AsyncHydraDB | None:
    if not API_KEY:
        return None
    return AsyncHydraDB(token=API_KEY)


async def _with_retry(operation: Callable[[], Awaitable[T]], max_retries: int = 3) -> T:
    """Retry ``operation`` on transient failures (rate-limits, server errors,
    or transient network errors).  Raises on the last attempt regardless of
    error type.
    """
    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            return await operation()
        except ApiError as exc:
            status_code = getattr(exc, "status_code", None)
            if status_code not in RETRYABLE_STATUS_CODES or attempt == max_retries:
                raise
            last_exc = exc
        except Exception as exc:  # network errors, SDK changes, etc.
            if attempt == max_retries:
                raise
            last_exc = exc
        await asyncio.sleep(2 ** (attempt - 1))  # 1 s, 2 s, 4 s
    # Unreachable in normal flow, but satisfies the type-checker.
    raise last_exc or RuntimeError("HydraDB retry loop exhausted")


def _error_payload(exc: Exception) -> ErrorPayload:
    if isinstance(exc, ApiError):
        body = getattr(exc, "body", None)
        detail = body.get("detail") if isinstance(body, dict) else None
        return {
            "status_code": getattr(exc, "status_code", None),
            "error_code": detail.get("error_code") if isinstance(detail, dict) else None,
            "message": (detail.get("message") if isinstance(detail, dict) else None) or str(exc),
        }
    return {"message": str(exc)}


@overload
def _to_plain_data(value: dict[str, Any]) -> dict[str, Any]: ...
@overload
def _to_plain_data(value: None) -> None: ...
@overload
def _to_plain_data(value: str) -> str: ...
@overload
def _to_plain_data(value: int) -> int: ...
def _to_plain_data(value: Any) -> Any:
    """Convert HydraDB SDK response objects to plain dicts.

    Handles Pydantic v1 (.dict()) and v2 (.model_dump()) models.
    Scalars pass through unchanged.
    """
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "dict"):
        return value.dict()
    return value


async def write_interaction_to_hydradb(
    contact_email: str | None,
    contact_name: str | None,
    company: str | None,
    extracted: ExtractionResult,
    interaction_type: str,
    raw_text: str,
) -> dict[str, Any]:
    content = (
        f"{contact_name or 'Unknown contact'} at {company or 'Unknown company'}: "
        f"{extracted.get('summary') or raw_text[:800]}"
    )
    metadata = {
        "contact_email": contact_email,
        "contact_name": contact_name,
        "company": company,
        "interaction_type": interaction_type,
        "interaction_date": date.today().isoformat(),
        "topics_raised": extracted.get("topics", []),
        "sentiment_shift": extracted.get("sentiment_shift"),
    }
    save_local_contact({
        "contactEmail": contact_email or "",
        "contactName": contact_name or "",
        "company": company or "",
        "stance": extracted.get("stance") or "neutral",
        "lastInteraction": metadata["interaction_date"],
        "topics": metadata["topics_raised"],
    })

    if not API_KEY:
        return {"status": "skipped", "reason": "HYDRA_DB_API_KEY missing", "content": content, "metadata": metadata}

    client = _hydradb_client()
    if not client:
        return {"status": "skipped", "reason": "HydraDB client unavailable"}
    try:
        result = await _with_retry(
            lambda: client.upload.add_memory(
                tenant_id=TENANT_ID,
                sub_tenant_id=_sub_tenant_id(contact_email),
                memories=[
                    {
                        "text": content,
                        "infer": True,
                        "user_name": contact_name or contact_email or "unknown_contact",
                        "metadata": metadata,
                        "additional_metadata": {
                            "raw_text": raw_text[:4000],
                            "extracted": extracted,
                        },
                    }
                ],
            )
        )

        if contact_email:
            manifest_meta = {
                "contact_email": contact_email,
                "contact_name": contact_name or "",
                "company": company or "",
                "interaction_date": date.today().isoformat(),
            }
            try:
                await _with_retry(
                    lambda: client.upload.add_memory(
                        tenant_id=TENANT_ID,
                        sub_tenant_id="_contacts_manifest",
                        memories=[{
                            "text": f"Contact: {contact_name or contact_email} at {company or 'unknown'}",
                            "infer": True,
                            "user_name": contact_name or contact_email or "unknown",
                            "metadata": manifest_meta,
                        }],
                    )
                )
            except Exception as exc:
                print(f"HydraDB: manifest write failed (non-fatal) — {exc}")
                pass

    except Exception as exc:
        return {"status": "error", "transport": "python-sdk", "error": _error_payload(exc)}
    return {"status": "ok", "transport": "python-sdk", "data": _to_plain_data(result)}
