"""Durable outbox execution with bounded retry and crash-lease recovery."""

import json
from datetime import datetime, timedelta, timezone


class OutboxWorker:
    def __init__(self, store, service=None):
        self.store = store
        self.service = service

    def run_once(self, limit=50, max_attempts=5):
        from .service import TopicFacade

        now = datetime.now(timezone.utc)
        cutoff = (now - timedelta(minutes=5)).isoformat()
        with self.store.transaction():
            self.store.conn.execute(
                "UPDATE mp_outbox SET status='pending' WHERE status='processing' AND updated_at<?",
                (cutoff,),
            )
            rows = self.store.conn.execute(
                "SELECT * FROM mp_outbox WHERE status='pending' AND available_at<=? ORDER BY created_at LIMIT ?",
                (now.isoformat(), limit),
            ).fetchall()
        result = {"processed": 0, "failed": 0, "retrying": 0, "ids": []}
        for row in rows:
            with self.store.transaction():
                claim = self.store.conn.execute(
                    "UPDATE mp_outbox SET status='processing',attempts=attempts+1,updated_at=? WHERE id=? AND status='pending'",
                    (now.isoformat(), row["id"]),
                )
                if not claim.rowcount:
                    continue
            owned = None
            try:
                payload = json.loads(row["payload_json"])
                scope = (
                    payload.get("user_id")
                    or payload.get("scope", {}).get("user_id")
                    or "default"
                )
                service = self.service
                if service is None or service.user_id != scope:
                    owned = TopicFacade(self.store.path, user_id=scope)
                    service = owned
                kind = row["task_type"]
                if kind == "topic_projection":
                    topic_id = payload["topic_id"]
                    service._topic(topic_id)
                    with service.store.transaction():
                        service._refresh(topic_id)
                elif kind == "index_rebuild":
                    service.reindex()
                elif kind == "forget_cleanup":
                    target = payload["target"]
                    if target["type"] == "field":
                        service.forget_field(
                            payload["scope"]["event_id"], payload["scope"]["field_path"]
                        )
                    else:
                        service.forget(target["type"], target["id"])
                else:
                    raise ValueError("Unsupported task type: " + str(kind))
                with self.store.transaction():
                    self.store.conn.execute(
                        "UPDATE mp_outbox SET status='complete',last_error=NULL,updated_at=? WHERE id=?",
                        (datetime.now(timezone.utc).isoformat(), row["id"]),
                    )
                result["processed"] += 1
                result["ids"].append(row["id"])
            except Exception as exc:
                attempts = row["attempts"] + 1
                status = "failed" if attempts >= max_attempts else "pending"
                with self.store.transaction():
                    self.store.conn.execute(
                        "UPDATE mp_outbox SET status=?,last_error=?,available_at=?,updated_at=? WHERE id=?",
                        (
                            status,
                            str(exc),
                            (
                                now + timedelta(seconds=min(300, 2**attempts))
                            ).isoformat(),
                            now.isoformat(),
                            row["id"],
                        ),
                    )
                result["failed" if status == "failed" else "retrying"] += 1
            finally:
                if owned:
                    owned.store.close()
        return result

    def drain(self, limit=100):
        total = {"processed": 0, "failed": 0, "retrying": 0, "ids": []}
        for _ in range(limit):
            r = self.run_once()
            for key in ("processed", "failed", "retrying"):
                total[key] += r[key]
            total["ids"] += r["ids"]
            if not r["processed"] and not r["failed"]:
                break
        return total
