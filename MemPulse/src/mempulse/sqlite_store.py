"""SQLite source of truth, transactional topic updates, and Chinese FTS5."""

from __future__ import annotations
import json
import re
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from .models import Event, Topic, Tag, TagKind


def fts_tokens(text):
    parts = re.findall(r"[\u3400-\u9fff]+|[A-Za-z0-9_.-]+", str(text).lower())
    tokens = []
    for part in parts:
        if re.fullmatch(r"[\u3400-\u9fff]+", part):
            tokens.extend(part[i : i + 2] for i in range(max(1, len(part) - 1)))
        else:
            tokens.append(part)
    return sorted(set(tokens))


class SQLiteTopicStore:
    def __init__(self, path=".mempulse/memory.sqlite3"):
        self.path = Path(path)
        if str(path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA busy_timeout=5000")
        self.conn.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS topics(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,title TEXT NOT NULL,payload TEXT NOT NULL,updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,payload TEXT NOT NULL,occurred_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS event_topics(event_id TEXT PRIMARY KEY REFERENCES events(id),topic_id TEXT NOT NULL REFERENCES topics(id));
        CREATE TABLE IF NOT EXISTS ingestion_keys(user_id TEXT NOT NULL,key TEXT NOT NULL,event_id TEXT NOT NULL REFERENCES events(id),PRIMARY KEY(user_id,key));
        CREATE TABLE IF NOT EXISTS topic_vectors(topic_id TEXT PRIMARY KEY REFERENCES topics(id),model_revision TEXT NOT NULL,vector_json TEXT NOT NULL,updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS aliases(entity_kind TEXT NOT NULL,entity_id TEXT NOT NULL,alias TEXT NOT NULL,canonical TEXT NOT NULL,source_event_id TEXT,created_at TEXT NOT NULL,PRIMARY KEY(entity_kind,alias,canonical));
        CREATE VIRTUAL TABLE IF NOT EXISTS topics_fts USING fts5(topic_id UNINDEXED,title,goal,summary,tokenize='unicode61');
        CREATE TABLE IF NOT EXISTS topic_tags(topic_id TEXT REFERENCES topics(id),canonical TEXT,kind TEXT,role TEXT,confidence REAL,status TEXT,sources TEXT,PRIMARY KEY(topic_id,canonical));
        CREATE TABLE IF NOT EXISTS derived_from(derived_id TEXT,derived_kind TEXT,source_event_id TEXT,field_path TEXT,PRIMARY KEY(derived_id,derived_kind,source_event_id,field_path));
        CREATE TABLE IF NOT EXISTS mp_derived_from(derived_type TEXT NOT NULL,derived_id TEXT NOT NULL,source_type TEXT NOT NULL,source_id TEXT NOT NULL,relation TEXT NOT NULL DEFAULT 'DERIVED_FROM',created_at TEXT NOT NULL,PRIMARY KEY(derived_type,derived_id,source_type,source_id,relation));
        CREATE TABLE IF NOT EXISTS jobs(id INTEGER PRIMARY KEY,object_id TEXT,operation TEXT,state TEXT DEFAULT 'pending',error TEXT);
        CREATE VIRTUAL TABLE IF NOT EXISTS events_fts USING fts5(event_id UNINDEXED,content,tokenize='unicode61');
        CREATE INDEX IF NOT EXISTS events_user ON events(user_id,occurred_at);
        CREATE INDEX IF NOT EXISTS events_host_session ON events(user_id,json_extract(payload,'$.metadata.opencode_session_id'),occurred_at);
        CREATE INDEX IF NOT EXISTS topics_user ON topics(user_id,updated_at);
        CREATE INDEX IF NOT EXISTS tags_lookup ON topic_tags(canonical,status);
        PRAGMA user_version=1;
        """)
        if "user_id" not in [
            row[1] for row in self.conn.execute("PRAGMA table_info(aliases)")
        ]:
            self.conn.execute(
                "ALTER TABLE aliases ADD COLUMN user_id TEXT NOT NULL DEFAULT 'default'"
            )
            self.conn.commit()
        self._depth = 0
        self._vector_cache = {}
        self._vector_generation = 0

    @contextmanager
    def transaction(self):
        with self._lock:
            outer = self._depth == 0
            if outer:
                self.conn.execute("BEGIN IMMEDIATE")
            self._depth += 1
            try:
                yield
                if outer:
                    self.conn.commit()
            except Exception:
                if outer:
                    self.conn.rollback()
                raise
            finally:
                self._depth -= 1

    @staticmethod
    def _topic(row):
        data = json.loads(row["payload"])
        data["tags"] = [
            Tag(
                TagKind(t["kind"]),
                t["canonical"],
                t["value"],
                t.get("confidence", 1),
                tuple(t.get("source_event_ids", ())),
                t.get("status", "accepted"),
                t.get("role"),
                t.get("label"),
            )
            for t in data.get("tags", [])
        ]
        data["vector"] = tuple(data["vector"]) if data.get("vector") else None
        return Topic(**data)

    def list_topics(self, user_id):
        return [
            self._topic(r)
            for r in self.conn.execute(
                "SELECT payload FROM topics WHERE user_id=? ORDER BY updated_at DESC",
                (user_id,),
            )
        ]

    def get_topic(self, topic_id):
        row = self.conn.execute(
            "SELECT payload FROM topics WHERE id=?", (topic_id,)
        ).fetchone()
        return self._topic(row) if row else None

    def save_topic(self, topic):
        self._vector_generation += 1
        self._vector_cache.clear()
        with self.transaction():
            self.conn.execute(
                "INSERT INTO topics VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title,payload=excluded.payload,updated_at=excluded.updated_at",
                (
                    topic.topic_id,
                    topic.user_id,
                    topic.title,
                    json.dumps(topic.to_dict(), ensure_ascii=False),
                    topic.updated_at,
                ),
            )
            self.conn.execute(
                "DELETE FROM topic_tags WHERE topic_id=?", (topic.topic_id,)
            )
            self.conn.execute(
                "DELETE FROM topic_vectors WHERE topic_id=?", (topic.topic_id,)
            )
            self.conn.execute(
                "DELETE FROM topics_fts WHERE topic_id=?", (topic.topic_id,)
            )
            if topic.state != "archived":
                self.conn.execute(
                    "INSERT INTO topics_fts VALUES(?,?,?,?)",
                    (
                        topic.topic_id,
                        " ".join(fts_tokens(topic.title)),
                        " ".join(fts_tokens(topic.goal)),
                        " ".join(fts_tokens(topic.summary)),
                    ),
                )
                if topic.vector is not None:
                    self.conn.execute(
                        "INSERT INTO topic_vectors VALUES(?,?,?,?)",
                        (
                            topic.topic_id,
                            str(topic.metadata.get("model_revision", "unloaded")),
                            json.dumps(list(topic.vector)),
                            topic.updated_at,
                        ),
                    )
            self.conn.execute(
                "DELETE FROM derived_from WHERE derived_id=? AND derived_kind='topic'",
                (topic.topic_id,),
            )
            self.conn.execute(
                "DELETE FROM mp_derived_from WHERE derived_id=? AND derived_type='topic'",
                (topic.topic_id,),
            )
            for tag in topic.tags:
                self.conn.execute(
                    "INSERT INTO topic_tags VALUES(?,?,?,?,?,?,?)",
                    (
                        topic.topic_id,
                        tag.canonical,
                        tag.kind.value,
                        tag.role,
                        tag.confidence,
                        tag.status,
                        json.dumps(tag.source_event_ids),
                    ),
                )
            for event_id in topic.event_ids:
                self.conn.execute(
                    "INSERT OR IGNORE INTO derived_from VALUES(?,?,?,?)",
                    (topic.topic_id, "topic", event_id, "overview"),
                )
                self.conn.execute(
                    "INSERT OR IGNORE INTO mp_derived_from VALUES(?,?,?,?,?,?)",
                    (
                        "topic",
                        topic.topic_id,
                        "event",
                        event_id,
                        "DERIVED_FROM",
                        topic.updated_at,
                    ),
                )

    def get_event(self, event_id):
        row = self.conn.execute(
            "SELECT payload FROM events WHERE id=?", (event_id,)
        ).fetchone()
        return Event.from_mapping(json.loads(row["payload"])) if row else None

    def event_topic(self, event_id):
        row = self.conn.execute(
            "SELECT topic_id FROM event_topics WHERE event_id=?", (event_id,)
        ).fetchone()
        return row[0] if row else None

    def idempotent_event(self, user_id, key):
        row = self.conn.execute(
            "SELECT event_id FROM ingestion_keys WHERE user_id=? AND key=?",
            (user_id, key),
        ).fetchone()
        return row[0] if row else None

    def save_event(self, event, topic_id=None):
        with self.transaction():
            for alias in event.metadata.get("resource_aliases", []):
                if (
                    isinstance(alias, dict)
                    and alias.get("alias")
                    and alias.get("canonical")
                ):
                    self.add_alias(
                        "resource",
                        str(alias.get("canonical")),
                        str(alias.get("alias")),
                        str(alias.get("canonical")),
                        event.event_id,
                        event.user_id,
                    )
            self.conn.execute(
                "INSERT OR REPLACE INTO events VALUES(?,?,?,?)",
                (
                    event.event_id,
                    event.user_id,
                    json.dumps(event.to_dict(), ensure_ascii=False),
                    event.occurred_at,
                ),
            )
            if event.idempotency_key:
                self.conn.execute(
                    "INSERT OR IGNORE INTO ingestion_keys VALUES(?,?,?)",
                    (event.user_id, event.idempotency_key, event.event_id),
                )
            if topic_id:
                self.conn.execute(
                    "INSERT OR REPLACE INTO event_topics VALUES(?,?)",
                    (event.event_id, topic_id),
                )
            self.conn.execute(
                "DELETE FROM events_fts WHERE event_id=?", (event.event_id,)
            )
            self.conn.execute(
                "INSERT INTO events_fts VALUES(?,?)",
                (event.event_id, " ".join(fts_tokens(event.content))),
            )

    def list_events(self, topic_id):
        return [
            Event.from_mapping(json.loads(r[0]))
            for r in self.conn.execute(
                "SELECT e.payload FROM events e JOIN event_topics x ON x.event_id=e.id WHERE x.topic_id=? ORDER BY e.occurred_at,e.id",
                (topic_id,),
            )
        ]

    def search(self, query, limit=20, user_id="default"):
        tokens = fts_tokens(query)
        if not tokens:
            return []
        match = " OR ".join('"' + t.replace('"', '""') + '"' for t in tokens)
        rows = self.conn.execute(
            "SELECT e.payload,t.topic_id,bm25(events_fts) score FROM events_fts JOIN events e ON e.id=events_fts.event_id LEFT JOIN event_topics t ON t.event_id=e.id WHERE events_fts MATCH ? AND e.user_id=? ORDER BY score,e.occurred_at DESC LIMIT ?",
            (match, user_id, limit),
        ).fetchall()
        return [
            {
                **json.loads(r["payload"]),
                "topic_id": r["topic_id"],
                "score": -r["score"],
            }
            for r in rows
        ]

    def vector_candidates(self, vector, model_revision, user_id, limit=30):
        from .vector_index import VectorIndex

        version = self.conn.execute("PRAGMA data_version").fetchone()[0]
        key = (user_id, model_revision, version, self._vector_generation)
        if key not in self._vector_cache:
            rows = self.conn.execute(
                "SELECT v.topic_id,v.vector_json FROM topic_vectors v JOIN topics t ON t.id=v.topic_id WHERE t.user_id=? AND v.model_revision=? ORDER BY v.topic_id",
                (user_id, model_revision),
            ).fetchall()
            self._vector_cache.clear()
            self._vector_cache[key] = VectorIndex(
                [(r["topic_id"], json.loads(r["vector_json"])) for r in rows]
            )
        return [
            (self.get_topic(tid), score)
            for tid, score in self._vector_cache[key].search(vector, limit)
        ]

    def add_alias(
        self,
        entity_kind,
        entity_id,
        alias,
        canonical,
        source_event_id=None,
        user_id="default",
    ):
        self.conn.execute(
            "INSERT OR IGNORE INTO aliases(entity_kind,entity_id,alias,canonical,source_event_id,created_at,user_id) VALUES(?,?,?,?,?,datetime('now'),?)",
            (entity_kind, entity_id, alias, canonical, source_event_id, user_id),
        )

    def resolve_alias(self, entity_kind, value, user_id="default"):
        rows = self.conn.execute(
            "SELECT DISTINCT canonical FROM aliases WHERE entity_kind=? AND alias=? AND user_id=?",
            (entity_kind, value, user_id),
        ).fetchall()
        if len(rows) > 1:
            raise ValueError("Ambiguous alias; use a canonical resource/person id")
        return rows[0][0] if rows else value

    def close(self):
        self.conn.close()

    def candidate_topics(self, event, limit=50):
        """Bound SQL candidate loading before constructing the graph projection."""
        from .tags import event_tags

        if event.metadata.get("force_new"):
            return []
        selected = []

        def add(rows):
            for row in rows:
                tid = row[0]
                if tid and tid not in selected:
                    selected.append(tid)

        if event.topic_hint:
            add(
                self.conn.execute(
                    "SELECT id FROM topics WHERE user_id=? AND (id=? OR title=?) LIMIT 3",
                    (event.user_id, event.topic_hint, event.topic_hint),
                )
            )
        if event.metadata.get('project_ref'):
            add(self.conn.execute("SELECT id FROM topics WHERE user_id=? AND json_extract(payload,'$.state')!='archived' AND json_extract(payload,'$.metadata.project_ref')=? LIMIT 50",
                                  (event.user_id, event.metadata['project_ref'])))
        tags = [t.canonical for t in event_tags(event) if t.kind.value != "time"]
        if tags:
            placeholders = ",".join("?" for _ in tags)
            add(
                self.conn.execute(
                    "SELECT t.id FROM topics t JOIN topic_tags g ON g.topic_id=t.id WHERE t.user_id=? AND g.canonical IN ("
                    + placeholders
                    + ") AND g.status='accepted' AND json_extract(t.payload,'$.state')!='archived' GROUP BY t.id ORDER BY COUNT(*) DESC LIMIT 30",
                    (event.user_id, *tags),
                )
            )
        tokens = fts_tokens(event.content)
        if tokens:
            match = " OR ".join('"' + t.replace('"', '""') + '"' for t in tokens)
            add(
                self.conn.execute(
                    "SELECT x.topic_id FROM events_fts JOIN events e ON e.id=events_fts.event_id JOIN event_topics x ON x.event_id=e.id JOIN topics t ON t.id=x.topic_id WHERE events_fts MATCH ? AND e.user_id=? AND json_extract(t.payload,'$.state')!='archived' ORDER BY bm25(events_fts) LIMIT 30",
                    (match, event.user_id),
                )
            )
        if not selected:
            add(
                self.conn.execute(
                    "SELECT id FROM topics WHERE user_id=? AND json_extract(payload,'$.state')!='archived' ORDER BY updated_at DESC LIMIT 30",
                    (event.user_id,),
                )
            )
        return [self.get_topic(tid) for tid in selected[:limit]]
