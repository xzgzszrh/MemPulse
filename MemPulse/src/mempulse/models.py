"""Storage-neutral contracts used by TopicCore.

The models are intentionally serialisable with ``to_dict`` so they can be
passed through a future CLI/MCP boundary without leaking implementation types.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class Route(str, Enum):
    NEW = "NEW"
    RESUME = "RESUME"
    AMBIGUOUS = "AMBIGUOUS"
    ATTACH = "ATTACH"


class TagKind(str, Enum):
    PERSON = "person"
    RESOURCE = "resource"
    TIME = "time"
    KEYWORD = "keyword"
    VECTOR = "vector"


@dataclass(frozen=True)
class Tag:
    kind: TagKind
    canonical: str
    value: str
    confidence: float = 1.0
    source_event_ids: tuple[str, ...] = ()
    status: str = "accepted"  # accepted | pending | attribute
    role: str | None = None
    label: str | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("tag confidence must be between 0 and 1")

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "canonical": self.canonical,
            "value": self.value,
            "confidence": self.confidence,
            "source_event_ids": list(self.source_event_ids),
            "status": self.status,
            "role": self.role,
            "label": self.label,
        }


@dataclass
class Event:
    event_id: str
    user_id: str
    content: str
    session_id: str | None = None
    idempotency_key: str | None = None
    source_type: str = "conversation"
    app: str | None = None
    tool: str | None = None
    action: str | None = None
    status: str = "success"
    occurred_at: str = field(default_factory=utc_now)
    observed_at: str = field(default_factory=utc_now)
    valid_from: str | None = None
    valid_to: str | None = None
    topic_hint: str | None = None
    resource_ids: list[str] = field(default_factory=list)
    person_refs: list[str] = field(default_factory=list)
    requested_action: str | None = None
    alternatives: list[str] = field(default_factory=list)
    user_override: bool = False
    args_ref: str | None = None
    result_ref: str | None = None
    error_type: str | None = None
    permission_scope: str | None = None
    evidence_ref: str | None = None
    source_version: str | None = None
    explicit_scope: str | None = None
    is_fallback: bool = False
    fallback_reason: str | None = None
    sensitivity: str = "normal"
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "Event":
        """Parse an Event from CLI/MCP-like JSON while ignoring unknown fields."""
        names = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{key: value[key] for key in names if key in value})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Topic:
    topic_id: str
    user_id: str
    title: str
    goal: str = ""
    summary: str = ""
    state: str = "active"  # active | incomplete | archived
    revision: int = 1
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    event_ids: list[str] = field(default_factory=list)
    tags: list[Tag] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    # A normalised vector is optional until the embedding backend is wired in.
    vector: tuple[float, ...] | None = None

    def add_event(self, event_id: str) -> None:
        if event_id not in self.event_ids:
            self.event_ids.append(event_id)
            self.revision += 1
            self.updated_at = utc_now()

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic_id": self.topic_id,
            "user_id": self.user_id,
            "title": self.title,
            "goal": self.goal,
            "summary": self.summary,
            "state": self.state,
            "revision": self.revision,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "event_ids": list(self.event_ids),
            "tags": [tag.to_dict() for tag in self.tags],
            "metadata": self.metadata,
            "vector": list(self.vector) if self.vector is not None else None,
        }


@dataclass(frozen=True)
class Candidate:
    topic_id: str
    score: float
    vector_score: float = 0.0
    lexical_score: float = 0.0
    explicit_score: float = 0.0
    graph_score: float = 0.0
    temporal_score: float = 0.0
    contradiction: float = 0.0
    evidence: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic_id": self.topic_id,
            "score": round(self.score, 6),
            "features": {
                "D": round(self.vector_score, 6),
                "L": round(self.lexical_score, 6),
                "E": round(self.explicit_score, 6),
                "G": round(self.graph_score, 6),
                "H": round(self.temporal_score, 6),
                "C": round(self.contradiction, 6),
            },
            "evidence": list(self.evidence),
        }


@dataclass(frozen=True)
class ContextField:
    name: str
    value: Any = None
    status: str = "missing"  # present | missing | pending
    evidence_event_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "status": self.status,
            "evidence_event_ids": list(self.evidence_event_ids),
        }


@dataclass
class ContextPack:
    topic_id: str
    route: Route = Route.RESUME
    title: str = ""
    overview: str = ""
    directory: list[dict[str, Any]] = field(default_factory=list)
    fields: list[ContextField] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    candidates: list[Candidate] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    generated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic_id": self.topic_id,
            "route": self.route.value,
            "title": self.title,
            "overview": self.overview,
            "directory": self.directory,
            "fields": [field.to_dict() for field in self.fields],
            "events": self.events,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "missing": list(self.missing),
            "generated_at": self.generated_at,
        }


@dataclass(frozen=True)
class Resolution:
    route: Route
    topic_id: str | None
    candidates: tuple[Candidate, ...] = ()
    tags: tuple[Tag, ...] = ()
    pending_tags: tuple[Tag, ...] = ()
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "route": self.route.value,
            "topic_id": self.topic_id,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "tags": [tag.to_dict() for tag in self.tags],
            "pending_tags": [tag.to_dict() for tag in self.pending_tags],
            "reason": self.reason,
        }
