"""TopicCore facade: route events and assemble auditable recovery context."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Callable, Iterable, Protocol

from .graph import TagGraph, cosine
from .models import (
    Candidate,
    ContextField,
    ContextPack,
    Event,
    Resolution,
    Route,
    Tag,
    TagKind,
    Topic,
)
from .tags import event_tags, keywords_from_text, normalize_keyword, validate_topic_tags


class TopicStore(Protocol):
    def list_topics(self, user_id: str) -> list[Topic]: ...
    def get_topic(self, topic_id: str) -> Topic | None: ...
    def save_topic(self, topic: Topic) -> None: ...
    def get_event(self, event_id: str) -> Event | None: ...
    def save_event(self, event: Event, topic_id: str | None = None) -> None: ...
    def list_events(self, topic_id: str) -> list[Event]: ...


class InMemoryTopicStore:
    """Small reference adapter used by tests and a local smoke demo."""

    def __init__(self) -> None:
        self.topics: dict[str, Topic] = {}
        self.events: dict[str, Event] = {}
        self.event_topics: dict[str, str] = {}

    def list_topics(self, user_id: str) -> list[Topic]:
        return sorted(
            (topic for topic in self.topics.values() if topic.user_id == user_id),
            key=lambda topic: topic.updated_at,
            reverse=True,
        )

    def get_topic(self, topic_id: str) -> Topic | None:
        return self.topics.get(topic_id)

    def save_topic(self, topic: Topic) -> None:
        self.topics[topic.topic_id] = topic

    def get_event(self, event_id: str) -> Event | None:
        return self.events.get(event_id)

    def save_event(self, event: Event, topic_id: str | None = None) -> None:
        self.events[event.event_id] = event
        if topic_id:
            self.event_topics[event.event_id] = topic_id

    def list_events(self, topic_id: str) -> list[Event]:
        return sorted(
            (
                event
                for event_id, event in self.events.items()
                if self.event_topics.get(event_id) == topic_id
            ),
            key=lambda event: (event.occurred_at, event.event_id),
        )


class TopicCore:
    """Storage-independent TopicCore.

    ``embed`` is an optional callable returning an L2-normalised tuple. A
    production implementation should inject the frozen or TIDE BGE encoder;
    lexical and graph signals remain available when no model is loaded.
    """

    def __init__(
        self,
        store: TopicStore,
        *,
        embed: Callable[[str], tuple[float, ...]] | None = None,
        model_rev: str = "unloaded",
        theta_new: float = 0.22,
        delta_ambiguous: float = 0.08,
    ) -> None:
        self.store = store
        self.embed = embed
        self.model_rev = model_rev
        self.theta_new = theta_new
        self.delta_ambiguous = delta_ambiguous
        self.embedding_fallbacks = {}
        self.last_embedding_fallback = None
        self.graph = TagGraph()
        self._rebuild_graph()

    def _rebuild_graph(self) -> None:
        for topic in self._all_topics():
            self.graph.upsert_topic(topic)

    def _all_topics(self) -> list[Topic]:
        if hasattr(self.store, "list_all_topics"):
            return list(self.store.list_all_topics())  # type: ignore[attr-defined]
        users = (
            {
                topic.user_id
                for values in getattr(self.store, "topics", {}).values()
                for topic in [values]
            }
            if hasattr(self.store, "topics")
            else set()
        )
        if users:
            result: list[Topic] = []
            for user in users:
                result.extend(self.store.list_topics(user))
            return result
        return []

    def create_topic(
        self,
        *,
        user_id: str,
        title: str,
        goal: str = "",
        topic_id: str | None = None,
        metadata: dict | None = None,
        vector: tuple[float, ...] | None = None,
    ) -> Topic:
        topic = Topic(
            topic_id or f"topic_{uuid.uuid4().hex[:12]}",
            user_id,
            title,
            goal=goal,
            summary=goal or title,
            metadata=metadata or {},
            vector=vector,
        )
        self.store.save_topic(topic)
        self.graph.upsert_topic(topic)
        return topic

    def encode(self, text, *, query=False):
        if not self.embed:
            return None
        from .embeddings import EmbeddingInputError
        if query:
            self.last_embedding_fallback = None
        try:
            if query and hasattr(self.embed, "encode_query"):
                return self.embed.encode_query(text)
            return self.embed(text)
        except EmbeddingInputError as error:
            reason = str(error)
            self.embedding_fallbacks[reason] = self.embedding_fallbacks.get(reason, 0) + 1
            if query:
                self.last_embedding_fallback = reason
            return None

    @staticmethod
    def topic_text(topic):
        # Encode the stable matter identity, not all event text, changing paths,
        # timestamps, or opaque person IDs. State details are retrieved separately.
        parts = [topic.title[:120], (topic.metadata.get('identity_goal') or topic.goal)[:400]]
        parts.extend(str(value)[:100] for value in topic.metadata.get('identity_aliases', [])[:3])
        parts.extend(tag.value for tag in topic.tags if tag.kind == TagKind.KEYWORD and tag.status == 'accepted')
        return "\n".join(dict.fromkeys(part.strip() for part in parts if part and part.strip()))

    def embed_topic(self, topic):
        topic.vector = self.encode(self.topic_text(topic))
        if topic.vector is not None:
            topic.metadata["model_revision"] = self.model_rev
        else:
            topic.metadata.pop("model_revision", None)
        return topic.vector

    def _candidate_topics(self, event):
        if event.metadata.get("force_new"):
            return []
        topics = (
            self.store.candidate_topics(event)
            if hasattr(self.store, "candidate_topics")
            else self.store.list_topics(event.user_id)
        )
        by_id = {t.topic_id: t for t in topics}
        scores = {t.topic_id: 1 / (60 + i) for i, t in enumerate(topics, 1)}
        if self.embed and hasattr(self.store, "vector_candidates"):
            q = self.encode(event.content, query=True)
            for i, (topic, _score) in enumerate(
                self.store.vector_candidates(q, self.model_rev, event.user_id, 30) if q is not None else [], 1
            ):
                if topic:
                    by_id[topic.topic_id] = topic
                    scores[topic.topic_id] = scores.get(topic.topic_id, 0) + 1 / (
                        60 + i
                    )
        for topic in by_id.values():
            if event.topic_hint in (topic.topic_id, topic.title):
                scores[topic.topic_id] += 1
        return [
            by_id[tid] for tid in sorted(scores, key=lambda k: (-scores[k], k))[:50]
        ]

    def resolve_event(self, event: Event | dict) -> Resolution:
        if isinstance(event, dict):
            event = Event.from_mapping(event)
        existing = self.store.get_event(event.event_id)
        if existing is not None:
            topic_id = (
                self.store.event_topic(event.event_id)
                if hasattr(self.store, "event_topic")
                else getattr(self.store, "event_topics", {}).get(event.event_id)
            )
            return Resolution(
                Route.RESUME, topic_id, reason="idempotent event already exists"
            )
        topics = self._candidate_topics(event)
        self.graph = TagGraph()
        for topic in topics:
            self.graph.upsert_topic(topic)
        raw_tags = event_tags(event, model_rev=None)
        accepted_by_topic: dict[str, tuple[list[Tag], list[Tag], list[str]]] = {}
        candidates = self._score_candidates(event, raw_tags, topics)
        route, selected = self._route(candidates, event)
        topic_id = (
            selected[0].topic_id
            if route in (Route.RESUME, Route.ATTACH) and selected
            else None
        )
        if route == Route.NEW:
            topic = self.create_topic(
                user_id=event.user_id,
                title=self._title_for(event),
                goal=event.content,
            )
            topic_id = topic.topic_id
            self.embed_topic(topic)
            # Vector tags become valid after a stable topic ID exists.
            tags = event_tags(
                event,
                topic_id=topic_id,
                model_rev=self.model_rev if topic.vector else None,
            )
            accepted, pending, missing = validate_topic_tags(topic, tags)
            topic.tags = accepted
            topic.metadata["pending_tags"] = [tag.to_dict() for tag in pending]
            topic.metadata["missing_tag_kinds"] = missing
            topic.add_event(event.event_id)
            self.store.save_topic(topic)
            self.graph.upsert_topic(topic)
            self.store.save_event(event, topic_id)
            return Resolution(
                route,
                topic_id,
                tuple(candidates[:3]),
                tuple(accepted),
                tuple(pending),
                "no existing topic met continuation threshold",
            )
        tags = (
            event_tags(
                event,
                topic_id=topic_id,
                model_rev=self.model_rev if self.embed else None,
            )
            if topic_id
            else raw_tags
        )
        if topic_id:
            topic = self.store.get_topic(topic_id)
            if topic is not None:
                accepted, pending, missing = validate_topic_tags(
                    topic, list(topic.tags) + tags
                )
                topic.tags = accepted
                self.embed_topic(topic)
                if topic.vector is None:
                    topic.tags = [tag for tag in topic.tags if tag.kind != TagKind.VECTOR]
                    if 'vector' not in missing: missing.append('vector')
                    topic.state = 'incomplete'
                topic.metadata["pending_tags"] = [tag.to_dict() for tag in pending]
                topic.metadata["missing_tag_kinds"] = missing
                topic.add_event(event.event_id)
                self.store.save_topic(topic)
                self.graph.upsert_topic(topic)
                self.store.save_event(event, topic_id)
        if not topic_id:
            self.store.save_event(event)
        return Resolution(
            route,
            topic_id,
            tuple(candidates[:3]),
            tuple(topic.tags) if topic_id and topic is not None else tuple(tags),
            tuple(pending) if topic_id and topic is not None else (),
            "explicit attach"
            if route == Route.ATTACH
            else "best continuation candidate",
        )

    def _score_candidates(
        self, event: Event, raw_tags: list[Tag], topics: list[Topic]
    ) -> list[Candidate]:
        if not topics:
            return []
        query_terms = keywords_from_text(event.content)
        query_vector = self.encode(event.content, query=True)
        exact = self.graph.exact_candidates(raw_tags)
        graph_scores, graph_evidence, _ = self.graph.paths_from_tags(raw_tags)
        scored: list[Candidate] = []
        for topic in topics:
            topic_terms = keywords_from_text(
                " ".join((topic.title, topic.goal, topic.summary))
            )
            lexical = len(query_terms & topic_terms) / max(
                1, len(query_terms | topic_terms)
            )
            explicit_tags = set(tag.canonical for tag in raw_tags) & set(
                tag.canonical for tag in topic.tags
            )
            explicit = min(
                1.0,
                len(explicit_tags)
                / max(1, len(set(tag.canonical for tag in raw_tags))),
            )
            if event.topic_hint and event.topic_hint in (topic.topic_id, topic.title):
                explicit = 1.0
            vector_score = (
                cosine(query_vector, topic.vector)
                if query_vector
                and topic.vector
                and topic.metadata.get("model_revision") == self.model_rev
                else 0.0
            )
            graph_score = min(1.0, graph_scores.get(topic.topic_id, 0.0))
            temporal = self._temporal_score(event, topic)
            contradiction = self._contradiction(event, topic)
            score = (
                0.40 * vector_score
                + 0.10 * lexical
                + 0.25 * explicit
                + 0.15 * graph_score
                + 0.10 * temporal
                - 0.35 * contradiction
            )
            evidence = tuple(sorted(explicit_tags)) + tuple(
                graph_evidence.get(topic.topic_id, ())
            )
            if topic.topic_id in exact and topic.topic_id not in graph_evidence:
                evidence += exact[topic.topic_id]
            scored.append(
                Candidate(
                    topic.topic_id,
                    score,
                    vector_score,
                    lexical,
                    explicit,
                    graph_score,
                    temporal,
                    contradiction,
                    tuple(dict.fromkeys(evidence)),
                )
            )
        return sorted(scored, key=lambda item: (-item.score, item.topic_id))

    def _route(
        self, candidates: list[Candidate], event: Event
    ) -> tuple[Route, list[Candidate]]:
        if event.metadata.get("force_new"):
            return Route.NEW, []
        attach = event.metadata.get("attach_only") or event.action in {
            "attach",
            "add_material",
        }
        explicit = next((item for item in candidates if event.topic_hint == item.topic_id), None)
        if explicit is not None:
            return (Route.ATTACH if attach else Route.RESUME), [explicit]
        # The delivered retrieval encoder has no accepted routing calibration.
        # Explicit host/session bindings still work; vector ranks never mutate a binding.
        if self.embed and not getattr(self.embed, "automatic_binding_allowed", True):
            return Route.AMBIGUOUS, candidates[:3]
        resume_cue = bool(
            re.search(r"继续|恢复|接着|之前|昨天|resume|continue", event.content, re.I)
        )
        if not candidates:
            return (Route.AMBIGUOUS if resume_cue else Route.NEW), []
        first = candidates[0]
        second = candidates[1].score if len(candidates) > 1 else 0.0
        if first.score < self.theta_new:
            return (Route.AMBIGUOUS if resume_cue else Route.NEW), candidates[:3]
        if first.score - second < self.delta_ambiguous:
            return Route.AMBIGUOUS, candidates[:3]
        return (Route.ATTACH if attach else Route.RESUME), [first]

    @staticmethod
    def _title_for(event: Event) -> str:
        text = re.sub(r"\s+", " ", event.content).strip()
        return str(event.metadata.get("title") or text[:80] or "未命名话题")

    @staticmethod
    def _temporal_score(event: Event, topic: Topic) -> float:
        try:
            current = datetime.fromisoformat(event.occurred_at.replace("Z", "+00:00"))
            previous = datetime.fromisoformat(topic.updated_at.replace("Z", "+00:00"))
            if current.tzinfo is None:
                current = current.replace(tzinfo=timezone.utc)
            if previous.tzinfo is None:
                previous = previous.replace(tzinfo=timezone.utc)
            days = abs((current - previous).total_seconds()) / 86400
            return max(0.0, min(1.0, 1.0 - days / 30.0))
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def _contradiction(event: Event, topic: Topic) -> float:
        # Explicit customer/project markers are strong negative evidence.
        # This prevents the demo pair 甲/乙 from collapsing into one topic
        # even before a trained TIDE encoder is available.
        markers = set("甲乙丙丁戊己庚辛壬癸")
        event_markers = markers & set(event.content)
        topic_markers = markers & set(topic.title + " " + topic.goal)
        if event_markers and topic_markers and event_markers.isdisjoint(topic_markers):
            return 0.95
        if event.topic_hint and event.topic_hint not in (topic.topic_id, topic.title):
            return 0.8
        existing_people = {
            tag.value for tag in topic.tags if tag.kind == TagKind.PERSON
        }
        event_people = {str(value.get('id', '') if isinstance(value, dict) else value).removeprefix("person:").lower()
                        for value in event.person_refs}
        if event_people and existing_people and not (event_people & existing_people):
            return 0.35
        return 0.0

    def restore(self, topic_id: str, *, event_limit: int = 20) -> ContextPack:
        topic = self.store.get_topic(topic_id)
        if topic is None:
            raise KeyError(f"unknown topic: {topic_id}")
        events = self.store.list_events(topic_id)
        fields = self._context_fields(topic, events)
        missing = [field.name for field in fields if field.status != "present"]
        directory = [
            {
                "event_id": event.event_id,
                "occurred_at": event.occurred_at,
                "action": event.action,
                "status": event.status,
            }
            for event in events
        ]
        return ContextPack(
            topic.topic_id,
            Route.RESUME,
            topic.title,
            topic.summary or topic.goal,
            directory,
            fields,
            [event.to_dict() for event in events[-event_limit:]],
            missing=missing,
        )

    @staticmethod
    def _context_fields(topic: Topic, events: list[Event]) -> list[ContextField]:
        metadata = topic.metadata

        def field(name: str, keys: tuple[str, ...]) -> ContextField:
            for key in keys:
                value = metadata.get(key)
                if value not in (None, "", [], {}):
                    evidence = tuple(
                        event.event_id
                        for event in events
                        if key in event.metadata
                        or event.metadata.get("context", {}).get(key) is not None
                    )
                    return ContextField(name, value, "present", evidence)
            return ContextField(name)

        result = [
            field("input_files", ("input_files", "files", "resource_ids")),
            field("template_version", ("template_version", "template")),
            field(
                "output_preference",
                ("output_preference", "output_format", "preference"),
            ),
            field("completed_steps", ("completed_steps", "done")),
            field("pending_steps", ("pending_steps", "todo", "next_steps")),
        ]
        # Event metadata is a valid fallback evidence source for imported topics.
        for index, item in enumerate(result):
            if item.status == "present":
                continue
            aliases = {
                "input_files": "input_files",
                "template_version": "template_version",
                "output_preference": "output_preference",
                "completed_steps": "completed_steps",
                "pending_steps": "pending_steps",
            }
            key = aliases[item.name]
            for event in reversed(events):
                value = event.metadata.get(key)
                if value not in (None, "", [], {}):
                    result[index] = ContextField(
                        item.name, value, "present", (event.event_id,)
                    )
                    break
        return result


__all__ = ["InMemoryTopicStore", "TopicCore", "TopicStore"]
