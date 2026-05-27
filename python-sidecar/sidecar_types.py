"""Shared TypedDict definitions replacing wildcard dict[str, Any] throughout the sidecar.

These types are structural — they document the shape, not enforce it at runtime.
All keys are total=False so downstream code that only reads partial data still type-checks.
"""

from typing import TypedDict


# ---------------------------------------------------------------------------
# Entity extraction (LLM response shape)
# ---------------------------------------------------------------------------

class CommitmentEntry(TypedDict, total=False):
    owner: str
    what: str
    status: str
    due: str
    source_quote: str


class RelationEntry(TypedDict, total=False):
    from_person: str
    to_person: str
    type: str
    evidence: str
    confidence: float


class UnresolvedEntry(TypedDict, total=False):
    holder: str
    awaiting_from: str
    what: str
    since: str


class ExtractionResult(TypedDict, total=False):
    people: list[str]
    companies: list[str]
    topics: list[str]
    commitments: list[CommitmentEntry]
    relations: list[RelationEntry]
    unresolved: list[UnresolvedEntry]
    stance: str
    sentiment_shift: str | None
    summary: str


# ---------------------------------------------------------------------------
# Contact shape (canonical, used across persistence / repo / API)
# ---------------------------------------------------------------------------

class ContactDict(TypedDict, total=False):
    contactEmail: str
    contactName: str
    company: str
    stance: str
    lastInteraction: str
    topics: list[str]
    sentimentShift: str
    commitments: list[CommitmentEntry]
    unresolved: list[UnresolvedEntry]
    summary: str
    interaction_date: str
    topics_raised: list[str]
    extracted: ExtractionResult


# ---------------------------------------------------------------------------
# WebSocket broadcast payloads
# ---------------------------------------------------------------------------

class WSTranscriptMessage(TypedDict):
    type: str  # "transcript"
    text: str


class WSBriefMessage(TypedDict):
    type: str  # "brief"
    data: dict[str, object]


class WSErrorMessage(TypedDict):
    type: str  # "error"
    message: str


class WSIngestCompleteMessage(TypedDict):
    type: str  # "ingest_complete"
    count: int


WSMessage = WSTranscriptMessage | WSBriefMessage | WSErrorMessage | WSIngestCompleteMessage


# ---------------------------------------------------------------------------
# Calendar meeting
# ---------------------------------------------------------------------------

class MeetingInfo(TypedDict, total=False):
    event_id: str
    summary: str
    contact_email: str
    contact_name: str
    company: str
    start_time: str


# ---------------------------------------------------------------------------
# OpenRouter response
# ---------------------------------------------------------------------------

class OpenRouterChoiceMessage(TypedDict):
    content: str


class OpenRouterChoice(TypedDict):
    message: OpenRouterChoiceMessage


class OpenRouterResponse(TypedDict):
    choices: list[OpenRouterChoice]


# ---------------------------------------------------------------------------
# HydraDB error payload
# ---------------------------------------------------------------------------

class ErrorPayload(TypedDict, total=False):
    status_code: int | None
    error_code: str | None
    message: str


# ---------------------------------------------------------------------------
# Graph data
# ---------------------------------------------------------------------------

class GraphEdge(TypedDict, total=False):
    from_person: str
    to_person: str
    type: str
    weight: float
    color: str
    evidence: list[dict[str, str]]


class GraphNode(TypedDict, total=False):
    id: str
    label: str
    importance: float
    type: str


class GraphData(TypedDict, total=False):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class DeviceInfo(TypedDict):
    index: int
    name: str
    channels: int
    default_samplerate: float


# ---------------------------------------------------------------------------
# API response wrappers
# ---------------------------------------------------------------------------

class ContactsResponse(TypedDict, total=False):
    contacts: list[ContactDict]
    source: str
    warning: str
    error: str
