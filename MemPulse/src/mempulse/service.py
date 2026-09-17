"""Application boundary shared by CLI, HTTP and MCP."""

from __future__ import annotations
import json
import os
import re
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from .core import TopicCore
from .graph import TagGraph
from .models import Event, Route
from .tags import event_tags, extract_keywords, keywords_from_text, normalize_person
from .sqlite_store import SQLiteTopicStore
from .governance import Governance


from .maintenance import TopicMaintenance


class TopicFacade(TopicMaintenance):
    def __init__(
        self, db_path=None, user_id="default", embed=None, model_rev="unloaded", model_config=None
    ):
        self.user_id = user_id
        self.strict_tags = os.environ.get("MEMPULSE_STRICT_TAGS") == "1"
        model_config = model_config or {}
        model_dir = model_config.get("model_dir") or os.environ.get("MEMPULSE_MODEL_DIR")
        if embed is None and model_dir:
            from .embeddings import OnnxEncoder

            embed = OnnxEncoder(model_dir, precision=model_config.get("precision") or os.environ.get("MEMPULSE_MODEL_PRECISION", "fp32"))
            model_rev = embed.revision
        self.store = SQLiteTopicStore(
            db_path or os.environ.get("MEMPULSE_DB", ".mempulse/memory.sqlite3")
        )
        self.governance = Governance(self.store.conn)
        self.core = TopicCore(self.store, embed=embed, model_rev=model_rev)

    def _hidden_event(self, event_id):
        if self.governance.is_tombstoned(target_type="event", target_id=event_id):
            return True
        rows = self.store.conn.execute(
            "SELECT scope_json FROM mp_tombstones WHERE target_type='field' AND status IN ('blocked','processing')"
        )
        return any(json.loads(r[0]).get("event_id") == event_id for r in rows)

    def _topic(self, topic_id):
        topic = self.store.get_topic(topic_id)
        if not topic or topic.user_id != self.user_id:
            raise KeyError("topic not found in this user scope")
        if self.governance.is_tombstoned(target_type="topic", target_id=topic_id):
            raise KeyError("topic has been forgotten")
        if any(self._hidden_event(eid) for eid in topic.event_ids):
            raise KeyError("topic temporarily hidden while source cleanup completes")
        return topic

    def normalize_event(self, value):
        if not isinstance(value, dict):
            raise ValueError("event must be a JSON object")
        data = dict(value)
        data.setdefault("event_id", data.pop("id", None) or "event_" + uuid.uuid4().hex)
        data.setdefault("user_id", self.user_id)
        if data["user_id"] != self.user_id:
            raise ValueError("user scope mismatch")
        data.setdefault("content", data.pop("text", ""))
        if not isinstance(data["content"], str) or not data["content"].strip():
            raise ValueError("content must be a non-empty string")
        if len(json.dumps(data, ensure_ascii=False).encode()) > 1024 * 1024:
            raise ValueError("event exceeds 1 MiB")
        data["metadata"] = dict(data.get("metadata") or {})
        if data.get("topic_title"):
            data["metadata"]["title"] = data.pop("topic_title")
        if data.get("topic_id"):
            data["topic_hint"] = data.pop("topic_id")
        if "kind" in data:
            data.setdefault("source_type", data.pop("kind"))
        for name in ("resource_ids", "person_refs"):
            if not isinstance(data.get(name, []), list):
                raise ValueError(name + " must be a list")
        if (
            not isinstance(data.get("confidence", 1), (int, float))
            or not 0 <= data.get("confidence", 1) <= 1
        ):
            raise ValueError("confidence must be between 0 and 1")
        if data.get("status", "success") not in (
            "success",
            "failed",
            "failure",
            "cancelled",
            "pending",
            "pending_confirmation",
        ):
            raise ValueError("unsupported event status")
        for key in ("occurred_at", "observed_at", "valid_from", "valid_to"):
            if data.get(key):
                dt = datetime.fromisoformat(data[key].replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    raise ValueError(key + " requires a timezone")
                data[key] = dt.astimezone(timezone.utc).isoformat()
        # Credentials are never allowed to become prose memory. This is a
        # narrow deterministic filter, not a claim of exhaustive PII coverage.
        data["content"] = re.sub(
            r"\bsk-[A-Za-z0-9_-]{12,}", "[REDACTED_CREDENTIAL]", data["content"]
        )
        for key in list(data["metadata"]):
            if key.lower() in ("api_key", "password", "access_token", "secret"):
                data["metadata"][key] = "[REDACTED_CREDENTIAL]"
        data["metadata"].setdefault(
            "keywords",
            extract_keywords(data["metadata"].get("title", data["content"])),
        )
        data["resource_ids"] = [
            self.store.resolve_alias("resource", str(value), self.user_id)
            for value in data.get("resource_ids", [])
        ]
        return Event.from_mapping(data)

    def ingest(self, value):
        event = self.normalize_event(value)
        with self.store.transaction():
            existing_id = (
                self.store.idempotent_event(self.user_id, event.idempotency_key)
                if event.idempotency_key
                else None
            )
            existing_id = existing_id or (
                event.event_id if self.store.get_event(event.event_id) else None
            )
            if existing_id:
                previous = self.store.get_event(existing_id)
                if previous.user_id != self.user_id:
                    raise ValueError("event id already belongs to another scope")
                topic_id = self.store.event_topic(existing_id)
                hidden = self.governance.is_tombstoned(
                    target_type="event", target_id=existing_id
                )
                return {
                    "event_id": existing_id,
                    "topic_id": None if hidden else topic_id,
                    "route": "FORGOTTEN"
                    if hidden
                    else ("RESUME" if topic_id else "AMBIGUOUS"),
                    "duplicate": True,
                }
            if event.topic_hint:
                target = self.store.get_topic(event.topic_hint)
                if target and target.user_id != self.user_id:
                    raise ValueError("topic scope mismatch")
            result = self.core.resolve_event(event)
            if result.topic_id:
                for person in event.person_refs:
                    if isinstance(person, dict):
                        for alias in [person.get('name'), *person.get('aliases', [])]:
                            if alias:
                                self.store.add_alias('person', person['id'], str(alias), str(person['id']).removeprefix('person:').lower(), event.event_id, self.user_id)
                        tag = normalize_person(
                            person.get("id", ""), event.event_id, person.get("role")
                        )
                    else:
                        tag = normalize_person(str(person), event.event_id)
                    self.store.conn.execute(
                        "INSERT OR IGNORE INTO mp_participation(event_id,topic_id,person_id,role,status,occurred_at,user_scope,evidence_event_id,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                        (
                            event.event_id,
                            result.topic_id,
                            tag.value,
                            tag.role,
                            "confirmed",
                            event.occurred_at,
                            self.user_id,
                            event.event_id,
                            event.observed_at,
                        ),
                    )
                for resource in event.metadata.get('resources', []):
                    if not isinstance(resource, dict) or resource.get('id') not in event.resource_ids:
                        continue
                    for alias in [resource.get('name'), resource.get('path'), *resource.get('aliases', [])]:
                        if alias:
                            self.store.add_alias('resource', resource['id'], str(alias), resource['id'], event.event_id, self.user_id)
        return {
            **result.to_dict(),
            "event_id": event.event_id,
            "duplicate": False,
            "index_state": "candidate" if result.route == Route.AMBIGUOUS else "ready",
            "embedding_backend": "unloaded"
            if not self.core.embed
            else self.core.model_rev,
        }

    def resolve(self, query, context=None):
        event = self.normalize_event({"content": query, **(context or {})})
        topics = [
            t
            for t in self.core._candidate_topics(event)
            if t.state != "archived"
            and (not event.metadata.get('project_ref') or t.metadata.get('project_ref') == event.metadata['project_ref'])
            and (not self.strict_tags or t.state == "active")
            and not any(self._hidden_event(eid) for eid in t.event_ids)
            and not self.governance.is_tombstoned(
                target_type="topic", target_id=t.topic_id
            )
        ]
        self.core.graph = TagGraph()
        for topic in topics:
            self.core.graph.upsert_topic(topic)
        candidates = self.core._score_candidates(event, event_tags(event), topics)
        route, selected = self.core._route(candidates, event)
        return {
            "route": route.value,
            "topic_id": selected[0].topic_id
            if route in (Route.RESUME, Route.ATTACH) and selected
            else None,
            "candidates": [c.to_dict() for c in selected[:3]],
            "ranked_candidates": [c.to_dict() for c in candidates[:30]],
            "routing_policy": "retrieval_only" if self.core.embed and not getattr(self.core.embed, "automatic_binding_allowed", True) else "reference_thresholds",
            "embedding_fallback": self.core.last_embedding_fallback,
            "embedding_backend": "unloaded"
            if not self.core.embed
            else self.core.model_rev,
        }

    def context(self, query, topic_id=None):
        if topic_id:
            return self.restore(topic_id=topic_id)
        route = self.resolve(query)
        if route["route"] == "RESUME" and route.get("topic_id"):
            return {**self.restore(topic_id=route["topic_id"]), "route": route}
        return {
            "route": route,
            "topic_id": None,
            "fields": [],
            "events": [],
            "missing": ["topic_id"],
        }

    def run_tool(
        self,
        tool,
        action,
        result_json=None,
        status="success",
        topic_id=None,
        args_json=None,
        error_type=None,
        fallback_reason=None,
        requested_action=None,
        alternatives=None,
        user_override=False,
        idempotency_key=None,
    ):
        if status not in ("success", "failed", "cancelled", "pending_confirmation"):
            raise ValueError(
                "run status must be success, failed, cancelled or pending_confirmation"
            )
        result = (
            result_json
            if result_json is not None
            else {"error": error_type or "no result"}
        )
        text = json.dumps(
            {"tool": tool, "action": action, "result": result}, ensure_ascii=False
        )
        if len(text) > 128 * 1024:
            raise ValueError(
                "tool result exceeds 128 KiB; store an evidence_ref instead"
            )
        return self.ingest(
            {
                "content": text,
                "topic_id": topic_id,
                "source_type": "tool",
                "tool": tool,
                "action": action,
                "status": status,
                "result_ref": json.dumps(result, ensure_ascii=False),
                "args_ref": json.dumps(args_json, ensure_ascii=False)
                if args_json is not None
                else None,
                "error_type": error_type,
                "is_fallback": bool(fallback_reason),
                "fallback_reason": fallback_reason,
                "requested_action": requested_action,
                "alternatives": alternatives or [],
                "user_override": user_override,
                "idempotency_key": idempotency_key,
                "metadata": {"tool_outcome": True},
            }
        )

    def search(self, query, **kwargs):
        from .retrieval import search_evidence
        context = dict(kwargs.get('context') or {})
        for key in ('topic_id', 'project_ref', 'person_ids', 'person_names', 'resource_ids', 'resource_names', 'from_time', 'to_time', 'time_axis', 'reference_time', 'enumeration'):
            if kwargs.get(key) is not None:
                context[key] = kwargs[key]
        return search_evidence(self, query, max(1, min(int(kwargs.get('limit', 20)), 100)), context)

    def restore(self, topic_id=None, query=None):
        if not topic_id:
            route = self.resolve(query or "")
            if route["route"] != "RESUME":
                return {**route, "fields": [], "events": [], "missing": ["topic_id"]}
            topic_id = route["topic_id"]
        topic = self._topic(topic_id)
        pack = self.core.restore(topic_id, event_limit=20).to_dict()
        pack["events"] = [
            e
            for e in pack["events"]
            if not self.governance.is_tombstoned(
                target_type="event", target_id=e["event_id"]
            )
        ]
        pack["directory"] = [
            e
            for e in pack["directory"]
            if not self.governance.is_tombstoned(
                target_type="event", target_id=e["event_id"]
            )
        ]
        version = self.governance.resolve_knowledge(
            user_id=self.user_id,
            key="template_version",
            scope_id=topic_id,
            include_disputed=True,
        )
        preference = self.governance.resolve_preference(
            user_id=self.user_id, key="output_preference", topic_id=topic_id
        )
        for field in pack["fields"]:
            if field["name"] == "template_version" and version.get("found"):
                field.update(
                    value=version["value"] if version["status"] == "active" else None,
                    status="present" if version["status"] == "active" else "conflicted",
                    evidence_event_ids=[version["source"]["evidence_event_id"]]
                    if version["source"].get("evidence_event_id")
                    else [],
                )
            if field["name"] == "output_preference" and preference.get("found"):
                field.update(
                    value=preference["value"],
                    status="present",
                    evidence_event_ids=[preference["source"]["evidence_event_id"]]
                    if preference["source"].get("evidence_event_id")
                    else [],
                )
        pack["missing"] = [
            f["name"] for f in pack["fields"] if f["status"] != "present"
        ]
        pack["knowledge_resolution"] = version
        pack["topic_revision"] = topic.revision
        from ._vendor.episodic_fingerprint import compute_fingerprint

        pack["fingerprint"] = compute_fingerprint(
            topic_id,
            {
                "mode": "topic_local",
                "active_topic_start_node_id": topic_id,
                "included_node_ids": [e["event_id"] for e in pack["events"]],
                "reactivation_decision": "RESUME",
                "reactivation_reason": str(topic.revision),
            },
        ).hash
        pack["checkpoint"] = self.governance.get_checkpoint(
            user_id=self.user_id, topic_id=topic_id
        )
        pack["embedding_backend"] = (
            "unloaded" if not self.core.embed else self.core.model_rev
        )
        return pack

    def list_topics(self):
        return {
            "topics": [
                t.to_dict()
                for t in self.store.list_topics(self.user_id)
                if t.state != "archived"
                and not any(self._hidden_event(eid) for eid in t.event_ids)
                and not self.governance.is_tombstoned(
                    target_type="topic", target_id=t.topic_id
                )
            ]
        }

    def update_preference(self, evidence):
        value = dict(evidence)
        value["user_id"] = self.user_id
        if value.get("scope_type") == "topic":
            self._topic(value.get("scope_id"))
        event_id = value.get("evidence_event_id")
        if event_id:
            event = self.store.get_event(event_id)
            if not event or event.user_id != self.user_id:
                raise ValueError("evidence not found")
            if event.is_fallback or event.status != "success":
                value["choice_type"] = "fallback"
        return self.governance.record_preference(**value)

    def resolve_preference(self, **query):
        query["user_id"] = self.user_id
        return self.governance.resolve_preference(**query)

    def knowledge(self, value):
        value = dict(value)
        value["user_id"] = self.user_id
        if value.get("scope_type", "topic") == "topic":
            self._topic(value.get("scope_id"))
        return self.governance.record_knowledge(**value)

    def checkpoint(self, topic_id, payload=None, pending_operation_keys=()):
        self._topic(topic_id)
        pack = dict(payload) if payload is not None else self.restore(topic_id)
        pack.pop("checkpoint", None)
        return self.governance.save_checkpoint(
            user_id=self.user_id,
            topic_id=topic_id,
            payload=pack,
            pending_operation_keys=pending_operation_keys,
        )

    def forget(self, target_type, target_id):
        if target_type not in ("event", "topic"):
            raise ValueError("supported targets: event or topic")
        if target_type == "topic":
            topic = self._topic(target_id)
            ids = [e.event_id for e in self.store.list_events(target_id)]
        else:
            event = self.store.get_event(target_id)
            if not event or event.user_id != self.user_id:
                raise KeyError("event not found in scope")
            ids = [target_id]
        receipt = self.governance.create_tombstone(
            target_type=target_type,
            target_id=target_id,
            scope={"user_id": self.user_id},
            requested_by=self.user_id,
        )
        touched = set()
        with self.store.transaction():
            for event_id in ids:
                tid = self.store.event_topic(event_id)
                if tid:
                    touched.add(tid)
                event = self.store.get_event(event_id)
                event.content = "[FORGOTTEN]"
                event.metadata = {}
                event.person_refs = []
                event.resource_ids = []
                self.store.save_event(event, tid)
                self.store.conn.execute(
                    "DELETE FROM events_fts WHERE event_id=?", (event_id,)
                )
                self.store.conn.execute(
                    "UPDATE mp_participation SET status='redacted' WHERE event_id=?",
                    (event_id,),
                )
                self.store.conn.execute(
                    "DELETE FROM mp_preferences WHERE evidence_event_id=?", (event_id,)
                )
                self.store.conn.execute(
                    "UPDATE mp_knowledge SET value_json='null',status='retracted' WHERE evidence_event_id=?",
                    (event_id,),
                )
            for tid in touched:
                topic = self.store.get_topic(tid)
                remaining = [
                    e
                    for e in self.store.list_events(tid)
                    if e.event_id not in ids and e.content != "[FORGOTTEN]"
                ]
                topic.event_ids = [e.event_id for e in remaining]
                identity=topic.metadata.get('confirmation_operation')
                keep_identity=bool(topic.metadata.get('identity_confirmed') and remaining and
                                   (not identity or identity+':identity' not in ids))
                if not keep_identity:
                    topic.title = (remaining[0].metadata.get("title", remaining[0].content[:80]) if remaining else "已遗忘的话题")
                    topic.summary = topic.goal = remaining[0].content if remaining else ""
                    topic.metadata = {}
                topic.tags = [
                    replace(
                        t,
                        source_event_ids=tuple(
                            e for e in t.source_event_ids if e not in ids
                        ),
                    )
                    for t in topic.tags
                    if any(e not in ids for e in t.source_event_ids)
                ]
                topic.vector = None
                topic.tags = [tag for tag in topic.tags if tag.kind.value!='vector']
                topic.metadata.pop('model_revision',None)
                topic.revision += 1
                topic.state = "incomplete" if remaining else "archived"
                self.store.save_topic(topic)
                self.store.conn.execute(
                    "DELETE FROM mp_checkpoints WHERE user_id=? AND topic_id=?",
                    (self.user_id, tid),
                )
            self.store.conn.execute(
                "UPDATE mp_outbox SET status='complete' WHERE idempotency_key=?",
                ("forget:" + receipt["id"],),
            )
        if self.core.embed and hasattr(self.core.embed,'cache'): self.core.embed.cache.clear()
        return self.governance.complete_tombstone(receipt["id"], residuals=())

    def query_relations(self, person_a, person_b, **kwargs):
        kwargs["user_scope"] = self.user_id
        return self.governance.enumerate_joint_participation(
            person_ids=[person_a, person_b], **kwargs
        )

    def reindex(self, topic_ids=None):
        if not self.core.embed:
            raise RuntimeError(
                "No local ONNX embedder configured; set MEMPULSE_MODEL_DIR"
            )
        count = 0
        skipped = []
        with self.store.transaction():
            targets=self.store.list_topics(self.user_id) if topic_ids is None else [self._topic(topic_id) for topic_id in dict.fromkeys(topic_ids)]
            for topic in targets:
                if topic.state == "archived":
                    continue
                self.core.embed_topic(topic)
                from .tags import normalize_vector, validate_topic_tags
                tags = [tag for tag in topic.tags if tag.kind.value != 'vector']
                if topic.vector is not None and topic.event_ids:
                    tags.append(replace(normalize_vector(topic.topic_id, self.core.model_rev),
                                        source_event_ids=tuple(topic.event_ids)))
                accepted, pending, missing = validate_topic_tags(topic, tags)
                topic.tags = accepted
                topic.metadata['missing_tag_kinds'] = missing
                topic.metadata['pending_tags'] = [tag.to_dict() for tag in pending] + topic.metadata.get('pending_tags', [])
                topic.revision += 1
                self.store.save_topic(topic)
                if topic.vector is None:
                    skipped.append(topic.topic_id)
                else:
                    count += 1
        self.core.graph = TagGraph()
        self.core._rebuild_graph()
        return {
            "status": "complete",
            "topics_reindexed": count,
            "model_revision": self.core.model_rev,
            "topics_skipped": skipped,
        }

    def configure_model(self, model_dir, precision="fp32"):
        from .embeddings import OnnxEncoder
        encoder = OnnxEncoder(model_dir, precision=precision)
        if precision == "mixed-int8":
            reference = OnnxEncoder(model_dir, precision="fp32", cache_size=0)
            probes = ["夜班清洁那部分水量该放在哪个时段？", "继续昨天的交付验收材料"]
            expected = reference.encode_batch(probes, query=True)
            actual = encoder.encode_batch(probes, query=True)
            similarity = min(sum(a * b for a, b in zip(left, right)) for left, right in zip(expected, actual))
            if similarity < 0.99:
                raise ValueError(f"mixed INT8 failed local FP32 parity (minimum cosine={similarity:.6f}); current model remains unchanged")
        previous = self.core
        self.core = TopicCore(self.store, embed=encoder, model_rev=encoder.revision)
        try:
            result = self.reindex()
        except Exception:
            self.core = previous
            raise
        return {**result, "embedding": encoder.info()}

    def health(self):
        sdk = {"backend": "not_configured", "status": "not_configured"}
        if os.environ.get("MEMPULSE_KYLIN_SDK"):
            from .kylin_sdk import KylinEmbeddingSDK

            sdk = (
                KylinEmbeddingSDK(
                    library=os.environ.get("MEMPULSE_KYLIN_SDK"),
                    model=os.environ.get("MEMPULSE_KYLIN_MODEL"),
                    dimension=int(os.environ["MEMPULSE_KYLIN_DIM"])
                    if os.environ.get("MEMPULSE_KYLIN_DIM")
                    else None,
                )
                .probe()
                .to_dict()
            )
        return {
            "ok": True,
            "service": "MemPulse",
            "storage": "sqlite",
            "db": str(self.store.path),
            "scope": self.user_id,
            "topiccore": True,
            "embedding_backend": "unloaded"
            if not self.core.embed
            else self.core.model_rev,
            "sdk_status": sdk,
            "schema_version": 1,
            "index_policy": "strict" if self.strict_tags else "drafts_included",
            "embedding": self.core.embed.info() if hasattr(self.core.embed, "info") else None,
            "embedding_fallbacks": dict(self.core.embedding_fallbacks),
        }


# All transports share one SQLite connection; serialize the complete operation.
from functools import wraps


def _synchronized(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with self.store._lock:
            return method(self, *args, **kwargs)

    return call


for _name in (
    "ingest",
    "resolve",
    "search",
    "restore",
    "list_topics",
    "update_preference",
    "resolve_preference",
    "knowledge",
    "checkpoint",
    "forget",
    "query_relations",
    "health",
    "reindex",
    "configure_model",
    "move_event",
    "merge_topics",
    "split_topic",
    "forget_field",
):
    setattr(TopicFacade, _name, _synchronized(getattr(TopicFacade, _name)))


def create_facade(db_path=None, **kwargs):
    return TopicFacade(db_path, **kwargs)
