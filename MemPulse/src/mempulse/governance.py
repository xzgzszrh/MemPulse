"""SQLite governance primitives for MemPulse.

``Governance`` owns only ``mp_*`` tables and accepts an existing
``sqlite3.Connection``.  It deliberately returns plain dictionaries so the
service, CLI, MCP and WebUI layers can share the same contract.

Main entry points:

* ``record_preference`` / ``resolve_preference`` implement CPR scope ordering
  and prevent temporary requests or forced fallbacks from becoming durable
  preferences.
* ``record_knowledge`` / ``resolve_knowledge`` keep valid time, observation
  time, supersession and dispute state separate.
* ``save_checkpoint`` / ``get_checkpoint`` persist resumable topic state.
* ``add_derivation`` / ``create_tombstone`` provide dependency traversal and a
  deletion receipt.  The caller remains responsible for deleting/redacting
  event bodies, then marking the receipt complete.
* ``record_participation`` / ``enumerate_joint_participation`` enumerate exact
  same-event participation with a stable snapshot cursor, without Top-K.
"""

from __future__ import annotations

import base64
import binascii
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence


@contextmanager
def transaction(conn):
    """Respect the facade's outer transaction instead of committing it early."""
    if not conn.in_transaction:
        with conn:
            yield
        return
    name='governance_'+uuid.uuid4().hex
    conn.execute('SAVEPOINT '+name)
    try:
        yield
    except Exception:
        conn.execute('ROLLBACK TO '+name)
        conn.execute('RELEASE '+name)
        raise
    conn.execute('RELEASE '+name)


def _now() -> str:
    # Keep microseconds so multiple checkpoints/preferences created in one
    # transaction still have a deterministic newest-first ordering.
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _value(value: str | None, default: Any = None) -> Any:
    if value is None:
        return default
    return json.loads(value)


def _row(cursor: sqlite3.Cursor, row: Sequence[Any] | sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    if isinstance(row, sqlite3.Row):
        return dict(row)
    assert cursor.description is not None
    return {description[0]: row[index] for index, description in enumerate(cursor.description)}


def _decode_cursor(cursor: str) -> dict[str, Any]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii") + b"=" * (-len(cursor) % 4))
        value = json.loads(raw.decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError
        return value
    except (ValueError, UnicodeError, binascii.Error, json.JSONDecodeError) as exc:
        raise ValueError("invalid participation cursor") from exc


def _encode_cursor(value: Mapping[str, Any]) -> str:
    return base64.urlsafe_b64encode(_json(value).encode("utf-8")).decode("ascii").rstrip("=")


class Governance:
    """Governance facade backed by a caller-owned SQLite connection."""

    _SCOPE_RANK = {"global": 1, "app": 2, "topic": 3, "task": 4}

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS mp_preferences (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                pref_key TEXT NOT NULL,
                value_json TEXT NOT NULL,
                scope_type TEXT NOT NULL CHECK(scope_type IN ('task','topic','app','global')),
                scope_id TEXT NOT NULL DEFAULT '',
                choice_type TEXT NOT NULL,
                promoted INTEGER NOT NULL CHECK(promoted IN (0,1)),
                status TEXT NOT NULL,
                valid_from TEXT NOT NULL,
                valid_to TEXT,
                observed_at TEXT NOT NULL,
                evidence_event_id TEXT,
                reason TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS mp_pref_lookup
                ON mp_preferences(user_id,pref_key,scope_type,scope_id,status,valid_from,valid_to);

            CREATE TABLE IF NOT EXISTS mp_knowledge (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                knowledge_key TEXT NOT NULL,
                value_json TEXT NOT NULL,
                scope_type TEXT NOT NULL,
                scope_id TEXT NOT NULL DEFAULT '',
                valid_from TEXT NOT NULL,
                valid_to TEXT,
                observed_at TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('active','superseded','disputed','retracted')),
                supersedes TEXT REFERENCES mp_knowledge(id),
                evidence_event_id TEXT,
                dispute_reason TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS mp_knowledge_lookup
                ON mp_knowledge(user_id,knowledge_key,scope_type,scope_id,valid_from,valid_to,observed_at,status);

            CREATE TABLE IF NOT EXISTS mp_checkpoints (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                topic_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                event_watermark TEXT,
                pending_operations_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS mp_checkpoint_latest
                ON mp_checkpoints(user_id,topic_id,created_at DESC,id DESC);

            CREATE TABLE IF NOT EXISTS mp_tombstones (
                id TEXT PRIMARY KEY,
                target_type TEXT NOT NULL,
                target_id TEXT NOT NULL,
                scope_json TEXT NOT NULL,
                reason TEXT,
                requested_by TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                completed_at TEXT,
                receipt_json TEXT NOT NULL,
                UNIQUE(target_type,target_id,status)
            );
            CREATE INDEX IF NOT EXISTS mp_tombstone_target
                ON mp_tombstones(target_type,target_id,status);

            CREATE TABLE IF NOT EXISTS mp_derived_from (
                derived_type TEXT NOT NULL,
                derived_id TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_id TEXT NOT NULL,
                relation TEXT NOT NULL DEFAULT 'DERIVED_FROM',
                created_at TEXT NOT NULL,
                PRIMARY KEY(derived_type,derived_id,source_type,source_id,relation)
            );
            CREATE INDEX IF NOT EXISTS mp_derived_source
                ON mp_derived_from(source_type,source_id);

            CREATE TABLE IF NOT EXISTS mp_participation (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL,
                topic_id TEXT NOT NULL,
                person_id TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'participant',
                status TEXT NOT NULL DEFAULT 'confirmed',
                occurred_at TEXT NOT NULL,
                user_scope TEXT NOT NULL,
                evidence_event_id TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(event_id,person_id,user_scope)
            );
            CREATE INDEX IF NOT EXISTS mp_participation_lookup
                ON mp_participation(user_scope,person_id,status,occurred_at,event_id,seq);

            CREATE TABLE IF NOT EXISTS mp_outbox (
                id TEXT PRIMARY KEY,
                task_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                attempts INTEGER NOT NULL DEFAULT 0,
                available_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                idempotency_key TEXT UNIQUE,
                last_error TEXT
            );
            CREATE INDEX IF NOT EXISTS mp_outbox_ready
                ON mp_outbox(status,available_at,created_at);
            """
        )

    # ------------------------------------------------------------------ CPR
    def record_preference(
        self,
        *,
        user_id: str,
        key: str,
        value: Any,
        scope_type: str = "global",
        scope_id: str | None = None,
        choice_type: str = "explicit",
        valid_from: str | None = None,
        valid_to: str | None = None,
        observed_at: str | None = None,
        evidence_event_id: str | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """Record CPR evidence without promoting fallback or temporary choices.

        ``choice_type`` accepts ``explicit``, ``temporary``, ``fallback`` and
        ``safety_constraint``. Explicit choices are durable. Temporary choices
        are resolvable only inside their exact non-global scope. Fallbacks stay
        as audit evidence and never participate in preference resolution.
        """
        if scope_type not in self._SCOPE_RANK:
            raise ValueError(f"unsupported preference scope: {scope_type}")
        if choice_type not in {"explicit", "temporary", "fallback", "safety_constraint"}:
            raise ValueError(f"unsupported choice_type: {choice_type}")
        if scope_type != "global" and not scope_id:
            raise ValueError("scope_id is required for task/topic/app preferences")
        if choice_type == "temporary" and scope_type == "global":
            raise ValueError("temporary requests require a task, topic or app scope")
        timestamp = observed_at or _now()
        pref_id = f"pref_{uuid.uuid4().hex}"
        promoted = choice_type in {"explicit", "safety_constraint"}
        status = {
            "explicit": "active",
            "temporary": "transient",
            "fallback": "evidence_only",
            "safety_constraint": "constraint",
        }[choice_type]
        with transaction(self.conn):
            self.conn.execute(
                """INSERT INTO mp_preferences
                   (id,user_id,pref_key,value_json,scope_type,scope_id,choice_type,promoted,status,
                    valid_from,valid_to,observed_at,evidence_event_id,reason,created_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (pref_id, user_id, key, _json(value), scope_type, scope_id or "", choice_type,
                 int(promoted), status, valid_from or timestamp, valid_to, timestamp,
                 evidence_event_id, reason, _now()),
            )
        return {
            "id": pref_id,
            "user_id": user_id,
            "key": key,
            "value": value,
            "scope": {"type": scope_type, "id": scope_id},
            "choice_type": choice_type,
            "promoted": promoted,
            "status": status,
            "reason": reason or self._preference_reason(choice_type),
        }

    @staticmethod
    def _preference_reason(choice_type: str) -> str:
        return {
            "explicit": "explicit user choice",
            "temporary": "temporary requirement is not promoted",
            "fallback": "forced fallback is audit evidence only",
            "safety_constraint": "safety constraint is enforced separately from taste",
        }[choice_type]

    def resolve_preference(
        self,
        *,
        user_id: str,
        key: str,
        task_id: str | None = None,
        topic_id: str | None = None,
        app_id: str | None = None,
        at: str | None = None,
    ) -> dict[str, Any]:
        """Resolve current task → topic → app → global, with evidence."""
        at = at or _now()
        scopes = [("task", task_id), ("topic", topic_id), ("app", app_id), ("global", "")]
        clauses: list[str] = []
        params: list[Any] = [user_id, key, at, at]
        for scope_type, scope_id in scopes:
            if scope_id is not None:
                clauses.append("(scope_type=? AND scope_id=?)")
                params.extend((scope_type, scope_id))
        cursor = self.conn.execute(
            f"""SELECT * FROM mp_preferences
                WHERE user_id=? AND pref_key=? AND valid_from<=?
                  AND (valid_to IS NULL OR valid_to>?)
                  AND status IN ('active','constraint','transient')
                  AND ({' OR '.join(clauses)})
                ORDER BY observed_at DESC, created_at DESC""",
            params,
        )
        rows = [_row(cursor, row) for row in cursor.fetchall()]
        candidates = [row for row in rows if row is not None]
        if not candidates:
            return {"found": False, "key": key, "value": None, "source": None}
        # Transient evidence applies only to the explicitly requested exact scope.
        def rank(row: Mapping[str, Any]) -> tuple[int, int, str]:
            transient_bonus = 1 if row["status"] == "transient" else 0
            return (self._SCOPE_RANK[row["scope_type"]], transient_bonus, row["observed_at"])
        selected = max(candidates, key=rank)
        return {
            "found": True,
            "key": key,
            "value": _value(selected["value_json"]),
            "source": {
                "id": selected["id"],
                "scope": {"type": selected["scope_type"], "id": selected["scope_id"] or None},
                "choice_type": selected["choice_type"],
                "promoted": bool(selected["promoted"]),
                "evidence_event_id": selected["evidence_event_id"],
            },
        }

    # -------------------------------------------------------------- knowledge
    def record_knowledge(
        self,
        *,
        user_id: str,
        key: str,
        value: Any,
        scope_type: str = "topic",
        scope_id: str = "",
        valid_from: str | None = None,
        valid_to: str | None = None,
        observed_at: str | None = None,
        evidence_event_id: str | None = None,
        supersedes: str | None = None,
        disputed: bool = False,
        dispute_reason: str | None = None,
    ) -> dict[str, Any]:
        timestamp = observed_at or _now()
        effective = valid_from or timestamp
        if valid_to is not None and valid_to <= effective:
            raise ValueError("valid_to must be later than valid_from")
        knowledge_id = f"knowledge_{uuid.uuid4().hex}"
        status = "disputed" if disputed else "active"
        with transaction(self.conn):
            if supersedes:
                previous_cursor = self.conn.execute("SELECT * FROM mp_knowledge WHERE id=?", (supersedes,))
                previous = _row(previous_cursor, previous_cursor.fetchone())
                if previous is None:
                    raise KeyError(f"unknown superseded knowledge: {supersedes}")
                if (previous["user_id"], previous["knowledge_key"], previous["scope_type"], previous["scope_id"]) != (
                    user_id, key, scope_type, scope_id
                ):
                    raise ValueError("supersedes must refer to the same knowledge identity and scope")
                closing_time = previous["valid_to"]
                if closing_time is None or closing_time > effective:
                    closing_time = effective
                self.conn.execute(
                    "UPDATE mp_knowledge SET status='superseded',valid_to=? WHERE id=?",
                    (closing_time, supersedes),
                )
            self.conn.execute(
                """INSERT INTO mp_knowledge
                   (id,user_id,knowledge_key,value_json,scope_type,scope_id,valid_from,valid_to,
                    observed_at,status,supersedes,evidence_event_id,dispute_reason,created_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (knowledge_id, user_id, key, _json(value), scope_type, scope_id, effective, valid_to,
                 timestamp, status, supersedes, evidence_event_id, dispute_reason, _now()),
            )
        return {
            "id": knowledge_id, "key": key, "value": value, "scope": {"type": scope_type, "id": scope_id},
            "valid_from": effective, "valid_to": valid_to, "observed_at": timestamp,
            "status": status, "supersedes": supersedes, "evidence_event_id": evidence_event_id,
        }

    def resolve_knowledge(
        self,
        *,
        user_id: str,
        key: str,
        scope_type: str = "topic",
        scope_id: str = "",
        valid_at: str | None = None,
        known_at: str | None = None,
        include_disputed: bool = False,
    ) -> dict[str, Any]:
        valid_at = valid_at or _now()
        known_at = known_at or _now()
        statuses = ("active", "superseded", "disputed") if include_disputed else ("active", "superseded")
        placeholders = ",".join("?" for _ in statuses)
        cursor = self.conn.execute(
            f"""SELECT * FROM mp_knowledge
                WHERE user_id=? AND knowledge_key=? AND scope_type=? AND scope_id=?
                  AND valid_from<=? AND (valid_to IS NULL OR valid_to>?) AND observed_at<=?
                  AND status IN ({placeholders})
                ORDER BY observed_at DESC, created_at DESC""",
            (user_id, key, scope_type, scope_id, valid_at, valid_at, known_at, *statuses),
        )
        rows = [_row(cursor, row) for row in cursor.fetchall()]
        records = [row for row in rows if row is not None]
        if not records:
            return {"found": False, "key": key, "value": None, "status": "missing", "candidates": []}
        active = [row for row in records if row["status"] != "disputed"]
        selected = active[0] if active else records[0]
        distinct = {_json(_value(row["value_json"])) for row in records}
        status = "disputed" if len(distinct) > 1 or selected["status"] == "disputed" else "active"
        return {
            "found": True,
            "key": key,
            "value": _value(selected["value_json"]),
            "status": status,
            "source": self._knowledge_dict(selected),
            "candidates": [self._knowledge_dict(row) for row in records] if status == "disputed" else [],
        }

    @staticmethod
    def _knowledge_dict(row: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"], "value": _value(row["value_json"]), "valid_from": row["valid_from"],
            "valid_to": row["valid_to"], "observed_at": row["observed_at"], "status": row["status"],
            "supersedes": row["supersedes"], "evidence_event_id": row["evidence_event_id"],
            "dispute_reason": row["dispute_reason"],
        }

    # ------------------------------------------------------------- checkpoint
    def save_checkpoint(
        self,
        *,
        user_id: str,
        topic_id: str,
        payload: Mapping[str, Any],
        event_watermark: str | None = None,
        pending_operation_keys: Iterable[str] = (),
    ) -> dict[str, Any]:
        checkpoint_id = f"checkpoint_{uuid.uuid4().hex}"
        created_at = _now()
        pending = list(dict.fromkeys(pending_operation_keys))
        with transaction(self.conn):
            self.conn.execute(
                """INSERT INTO mp_checkpoints
                   (id,user_id,topic_id,payload_json,event_watermark,pending_operations_json,created_at)
                   VALUES(?,?,?,?,?,?,?)""",
                (checkpoint_id, user_id, topic_id, _json(dict(payload)), event_watermark, _json(pending), created_at),
            )
        return {"id": checkpoint_id, "user_id": user_id, "topic_id": topic_id,
                "payload": dict(payload), "event_watermark": event_watermark,
                "pending_operation_keys": pending, "created_at": created_at}

    def get_checkpoint(self, *, user_id: str, topic_id: str, checkpoint_id: str | None = None) -> dict[str, Any]:
        if checkpoint_id:
            cursor = self.conn.execute(
                "SELECT * FROM mp_checkpoints WHERE id=? AND user_id=? AND topic_id=?",
                (checkpoint_id, user_id, topic_id),
            )
        else:
            cursor = self.conn.execute(
                """SELECT * FROM mp_checkpoints WHERE user_id=? AND topic_id=?
                   ORDER BY created_at DESC,id DESC LIMIT 1""",
                (user_id, topic_id),
            )
        row = _row(cursor, cursor.fetchone())
        if row is None:
            return {"found": False, "topic_id": topic_id, "checkpoint": None}
        return {"found": True, "topic_id": topic_id, "checkpoint": {
            "id": row["id"], "payload": _value(row["payload_json"], {}),
            "event_watermark": row["event_watermark"],
            "pending_operation_keys": _value(row["pending_operations_json"], []),
            "created_at": row["created_at"],
        }}

    # --------------------------------------------------------- provenance/GDPR
    def add_derivation(
        self,
        *,
        derived_type: str,
        derived_id: str,
        source_type: str = "event",
        source_id: str,
        relation: str = "DERIVED_FROM",
    ) -> dict[str, Any]:
        with transaction(self.conn):
            self.conn.execute(
                """INSERT OR IGNORE INTO mp_derived_from
                   (derived_type,derived_id,source_type,source_id,relation,created_at)
                   VALUES(?,?,?,?,?,?)""",
                (derived_type, derived_id, source_type, source_id, relation, _now()),
            )
        return {"derived": {"type": derived_type, "id": derived_id},
                "source": {"type": source_type, "id": source_id}, "relation": relation}

    def dependent_closure(self, *, source_type: str, source_id: str, max_nodes: int = 10_000) -> list[dict[str, str]]:
        queue = [(source_type, source_id)]
        visited = {(source_type, source_id)}
        dependencies: list[dict[str, str]] = []
        while queue:
            current_type, current_id = queue.pop(0)
            rows = self.conn.execute(
                """SELECT derived_type,derived_id,relation FROM mp_derived_from
                   WHERE source_type=? AND source_id=? ORDER BY derived_type,derived_id""",
                (current_type, current_id),
            ).fetchall()
            for row in rows:
                derived_type, derived_id, relation = row[0], row[1], row[2]
                node = (derived_type, derived_id)
                if node in visited:
                    continue
                visited.add(node)
                dependencies.append({"type": derived_type, "id": derived_id, "relation": relation})
                if len(visited) > max_nodes:
                    raise RuntimeError("derivation graph exceeds traversal budget")
                queue.append(node)
        return dependencies

    def create_tombstone(
        self,
        *,
        target_type: str,
        target_id: str,
        reason: str | None = None,
        requested_by: str | None = None,
        scope: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        existing_cursor = self.conn.execute(
            """SELECT receipt_json FROM mp_tombstones
               WHERE target_type=? AND target_id=? AND status IN ('blocked','processing','complete')
               ORDER BY created_at DESC LIMIT 1""",
            (target_type, target_id),
        )
        existing = existing_cursor.fetchone()
        if existing:
            return _value(existing[0])
        dependencies = self.dependent_closure(source_type=target_type, source_id=target_id)
        tombstone_id = f"tombstone_{uuid.uuid4().hex}"
        created_at = _now()
        receipt = {
            "id": tombstone_id,
            "target": {"type": target_type, "id": target_id},
            "scope": dict(scope or {}),
            "status": "blocked",
            "query_visibility": "hidden",
            "dependencies": dependencies,
            "reason": reason,
            "requested_by": requested_by,
            "created_at": created_at,
        }
        outbox_id = f"outbox_{uuid.uuid4().hex}"
        with transaction(self.conn):
            self.conn.execute(
                """INSERT INTO mp_tombstones
                   (id,target_type,target_id,scope_json,reason,requested_by,status,created_at,receipt_json)
                   VALUES(?,?,?,?,?,?,?,?,?)""",
                (tombstone_id, target_type, target_id, _json(dict(scope or {})), reason,
                 requested_by, "blocked", created_at, _json(receipt)),
            )
            self.conn.execute(
                """INSERT INTO mp_outbox
                   (id,task_type,payload_json,status,attempts,available_at,created_at,updated_at,idempotency_key)
                   VALUES(?,?,?,?,?,?,?,?,?)""",
                (outbox_id, "forget_cleanup", _json(receipt), "pending", 0, created_at,
                 created_at, created_at, f"forget:{tombstone_id}"),
            )
        return receipt

    def is_tombstoned(self, *, target_type: str, target_id: str) -> bool:
        row = self.conn.execute(
            """SELECT 1 FROM mp_tombstones WHERE target_type=? AND target_id=?
               AND status IN ('blocked','processing','complete') LIMIT 1""",
            (target_type, target_id),
        ).fetchone()
        return row is not None

    def complete_tombstone(self, tombstone_id: str, *, residuals: Sequence[Mapping[str, Any]] = ()) -> dict[str, Any]:
        cursor = self.conn.execute("SELECT receipt_json FROM mp_tombstones WHERE id=?", (tombstone_id,))
        row = cursor.fetchone()
        if row is None:
            raise KeyError(f"unknown tombstone: {tombstone_id}")
        receipt = _value(row[0])
        receipt["residuals"] = [dict(item) for item in residuals]
        receipt["status"] = "complete" if not residuals else "blocked"
        completed_at = _now() if not residuals else None
        receipt["completed_at"] = completed_at
        with transaction(self.conn):
            self.conn.execute(
                "UPDATE mp_tombstones SET status=?,completed_at=?,receipt_json=? WHERE id=?",
                (receipt["status"], completed_at, _json(receipt), tombstone_id),
            )
        return receipt

    # ----------------------------------------------------------- participation
    def record_participation(
        self,
        *,
        event_id: str,
        topic_id: str,
        person_id: str,
        occurred_at: str,
        user_scope: str,
        role: str = "participant",
        status: str = "confirmed",
        evidence_event_id: str | None = None,
    ) -> dict[str, Any]:
        with transaction(self.conn):
            self.conn.execute(
                """INSERT INTO mp_participation
                   (event_id,topic_id,person_id,role,status,occurred_at,user_scope,evidence_event_id,created_at)
                   VALUES(?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(event_id,person_id,user_scope) DO UPDATE SET
                     topic_id=excluded.topic_id,role=excluded.role,status=excluded.status,
                     occurred_at=excluded.occurred_at,evidence_event_id=excluded.evidence_event_id""",
                (event_id, topic_id, person_id, role, status, occurred_at, user_scope,
                 evidence_event_id, _now()),
            )
        return {"event_id": event_id, "topic_id": topic_id, "person_id": person_id,
                "role": role, "status": status, "occurred_at": occurred_at,
                "user_scope": user_scope, "evidence_event_id": evidence_event_id}

    def enumerate_joint_participation(
        self,
        *,
        person_ids: Sequence[str],
        user_scope: str,
        from_time: str | None = None,
        to_time: str | None = None,
        limit: int = 100,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        """Return events where every requested person has confirmed evidence."""
        people = tuple(sorted(set(person_ids)))
        if not people:
            raise ValueError("person_ids cannot be empty")
        if limit < 1 or limit > 1000:
            raise ValueError("limit must be between 1 and 1000")
        state = _decode_cursor(cursor) if cursor else {}
        snapshot = int(state.get("snapshot") or self.conn.execute(
            "SELECT COALESCE(MAX(seq),0) FROM mp_participation WHERE user_scope=?", (user_scope,)
        ).fetchone()[0])
        after_time = state.get("occurred_at", "")
        after_event = state.get("event_id", "")
        placeholders = ",".join("?" for _ in people)
        filters = ["user_scope=?", "status='confirmed'", "seq<=?", f"person_id IN ({placeholders})"]
        params: list[Any] = [user_scope, snapshot, *people]
        if from_time:
            filters.append("occurred_at>=?")
            params.append(from_time)
        if to_time:
            filters.append("occurred_at<?")
            params.append(to_time)
        filters.append("(occurred_at>? OR (occurred_at=? AND event_id>?))")
        params.extend((after_time, after_time, after_event))
        params.extend((len(people), limit + 1))
        sql = f"""
            SELECT event_id,topic_id,occurred_at,
                   GROUP_CONCAT(person_id) AS people,
                   GROUP_CONCAT(role) AS roles,
                   COUNT(DISTINCT person_id) AS matched_people
            FROM mp_participation
            WHERE {' AND '.join(filters)}
            GROUP BY event_id,topic_id,occurred_at
            HAVING COUNT(DISTINCT person_id)=?
            ORDER BY occurred_at,event_id
            LIMIT ?
        """
        cursor_obj = self.conn.execute(sql, params)
        rows = [_row(cursor_obj, row) for row in cursor_obj.fetchall()]
        records = [row for row in rows if row is not None]
        complete = len(records) <= limit
        page = records[:limit]
        results = [{
            "event_id": row["event_id"], "topic_id": row["topic_id"], "occurred_at": row["occurred_at"],
            "person_ids": sorted(row["people"].split(",")), "roles": row["roles"].split(","),
        } for row in page]
        next_cursor = None
        if not complete and page:
            last = page[-1]
            next_cursor = _encode_cursor({"snapshot": snapshot, "occurred_at": last["occurred_at"],
                                          "event_id": last["event_id"]})
        pending = self.conn.execute(
            """SELECT COUNT(*) FROM mp_participation
               WHERE user_scope=? AND seq<=? AND status!='confirmed'""",
            (user_scope, snapshot),
        ).fetchone()[0]
        return {
            "results": results,
            "complete": complete,
            "next_cursor": next_cursor,
            "event_watermark": snapshot,
            "relationship_watermark": snapshot,
            "pending_evidence_count": pending,
        }
