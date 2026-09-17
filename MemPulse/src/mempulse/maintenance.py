"""Explicit topic operations and field-level evidence redaction."""

import json
from .tags import event_tags, validate_topic_tags


def scrub(value, needle):
    if isinstance(value, str):
        return value.replace(needle, "[FORGOTTEN]")
    if isinstance(value, list):
        return [scrub(v, needle) for v in value]
    if isinstance(value, dict):
        return {k: scrub(v, needle) for k, v in value.items()}
    return value


class TopicMaintenance:
    def _refresh(self, topic_id):
        topic = self.store.get_topic(topic_id)
        events = [
            e for e in self.store.list_events(topic_id) if e.content != "[FORGOTTEN]"
        ]
        topic.event_ids = [e.event_id for e in events]
        topic.tags = []
        topic.vector = None
        topic.revision += 1
        if events:
            if not topic.metadata.get('identity_confirmed'):
                topic.goal = topic.summary = events[0].content
            tags = [tag for e in events for tag in event_tags(e)]
            accepted, pending, missing = validate_topic_tags(topic, tags)
            topic.tags = accepted
            topic.metadata = {**topic.metadata,
                "pending_tags": [t.to_dict() for t in pending],
                "missing_tag_kinds": missing,
            }
            self.core.embed_topic(topic)
        else:
            topic.title = "已归档的话题"
            topic.goal = topic.summary = ""
            topic.state = "archived"
            topic.metadata = {}
        self.store.save_topic(topic)
        self.store.conn.execute(
            "DELETE FROM mp_checkpoints WHERE user_id=? AND topic_id=?",
            (self.user_id, topic_id),
        )
        return topic

    def move_event(self, event_id, topic_id):
        self._topic(topic_id)
        event = self.store.get_event(event_id)
        if not event or event.user_id != self.user_id:
            raise KeyError("event not found")
        if self.governance.is_tombstoned(target_type="event", target_id=event_id):
            raise ValueError("forgotten event cannot be moved")
        previous = self.store.event_topic(event_id)
        with self.store.transaction():
            self.store.save_event(event, topic_id)
            self.store.conn.execute(
                "UPDATE mp_participation SET topic_id=? WHERE event_id=? AND user_scope=?",
                (topic_id, event_id, self.user_id),
            )
            for tid in set([t for t in [previous, topic_id] if t]):
                self._refresh(tid)
        return {
            "event_id": event_id,
            "previous_topic": previous,
            "topic_id": topic_id,
            "status": "moved",
        }

    def merge_topics(self, source_id, target_id):
        if source_id == target_id:
            raise ValueError("source and target must differ")
        self._topic(source_id)
        self._topic(target_id)
        with self.store.transaction():
            for event in self.store.list_events(source_id):
                self.store.conn.execute(
                    "UPDATE event_topics SET topic_id=? WHERE event_id=?",
                    (target_id, event.event_id),
                )
            self.store.conn.execute(
                "UPDATE mp_participation SET topic_id=? WHERE topic_id=? AND user_scope=?",
                (target_id, source_id, self.user_id),
            )
            self._refresh(target_id)
            old = self._refresh(source_id)
            old.metadata["merged_into"] = target_id
            self.store.save_topic(old)
        return {"status": "merged", "source_id": source_id, "topic_id": target_id}

    def split_topic(self, topic_id, event_ids, title):
        self._topic(topic_id)
        selected = set(event_ids)
        if not selected or not title.strip():
            raise ValueError("select events and provide a title")
        own = {e.event_id for e in self.store.list_events(topic_id)}
        if not selected <= own:
            raise ValueError("event does not belong to source topic")
        with self.store.transaction():
            target = self.core.create_topic(
                user_id=self.user_id, title=title, metadata={"parent_id": topic_id}
            )
            for eid in selected:
                self.move_event(eid, target.topic_id)
        return {"status": "split", "parent_id": topic_id, "topic_id": target.topic_id}

    def forget_field(self, event_id, field_path):
        event = self.store.get_event(event_id)
        if not event or event.user_id != self.user_id:
            raise KeyError("event not found")
        if not field_path.startswith("metadata."):
            raise ValueError("field path must begin with metadata.")
        keys = field_path.split(".")[1:]
        data = event.to_dict()
        parent = data["metadata"]
        for key in keys[:-1]:
            if not isinstance(parent, dict) or key not in parent:
                raise KeyError("field not found")
            parent = parent[key]
        value = parent.get(keys[-1]) if isinstance(parent, dict) else None
        if not isinstance(value, str) or not value:
            raise ValueError("field must be a non-empty string")
        tid = self.store.event_topic(event_id)
        source_key = event_id + ":" + field_path
        if tid:
            self.governance.add_derivation(
                derived_type="topic",
                derived_id=tid,
                source_type="field",
                source_id=source_key,
            )
        receipt = self.governance.create_tombstone(
            target_type="field",
            target_id=source_key,
            scope={
                "user_id": self.user_id,
                "event_id": event_id,
                "field_path": field_path,
            },
            requested_by=self.user_id,
        )
        del parent[keys[-1]]
        from .models import Event

        with self.store.transaction():
            cleaned = Event.from_mapping(scrub(data, value))
            self.store.save_event(cleaned, tid)
            if tid:
                topic = self._refresh(tid)
                topic.title = scrub(topic.title,value)
                topic.goal = scrub(topic.goal,value)
                topic.summary = scrub(topic.summary,value)
                topic.metadata = scrub(topic.metadata,value)
                self.core.embed_topic(topic)
                self.store.save_topic(topic)
                self.core.graph.upsert_topic(topic)
            for table in ("mp_preferences", "mp_knowledge"):
                for row in self.store.conn.execute(
                    "SELECT id,value_json FROM "
                    + table
                    + " WHERE user_id=? AND evidence_event_id=?",
                    (self.user_id, event_id),
                ).fetchall():
                    cleaned_value = scrub(json.loads(row["value_json"]), value)
                    self.store.conn.execute(
                        "UPDATE " + table + " SET value_json=? WHERE id=?",
                        (json.dumps(cleaned_value, ensure_ascii=False), row["id"]),
                    )
            self.store.conn.execute(
                "UPDATE mp_outbox SET status='complete' WHERE idempotency_key=?",
                ("forget:" + receipt["id"],),
            )
        residuals = []
        if value in json.dumps(
            self.store.get_event(event_id).to_dict(), ensure_ascii=False
        ):
            residuals.append({"kind": "event", "id": event_id})
        if tid and value in json.dumps(
            self.store.get_topic(tid).to_dict(), ensure_ascii=False
        ):
            residuals.append({"kind": "topic", "id": tid})
        result = self.governance.complete_tombstone(receipt["id"], residuals=residuals)
        if self.core.embed and hasattr(self.core.embed,'cache'): self.core.embed.cache.clear()
        result["verification"] = (
            "literal-and-derived-objects; filesystem snapshots not erased"
        )
        return result
