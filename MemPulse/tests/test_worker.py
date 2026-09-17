import json
from datetime import datetime, timezone
from mempulse.service import TopicFacade
from mempulse.worker import OutboxWorker


def enqueue(f, kind, payload):
    now = datetime.now(timezone.utc).isoformat()
    with f.store.transaction():
        f.store.conn.execute(
            "INSERT INTO mp_outbox(id,task_type,payload_json,status,attempts,available_at,created_at,updated_at,idempotency_key) VALUES(?,?,?,?,?,?,?,?,?)",
            ("job", kind, json.dumps(payload), "pending", 0, now, now, now, "job"),
        )


def test_projection_worker_executes_rebuild(tmp_path):
    f = TopicFacade(tmp_path / "w.db")
    r = f.ingest({"content": "真实步骤", "metadata": {"force_new": True}})
    t = f.store.get_topic(r["topic_id"])
    t.summary = "stale"
    f.store.save_topic(t)
    enqueue(f, "topic_projection", {"topic_id": r["topic_id"]})
    assert OutboxWorker(f.store, f).run_once()["processed"] == 1
    assert f.store.get_topic(r["topic_id"]).summary == "真实步骤"
    f.store.close()


def test_unknown_job_retries_without_false_completion(tmp_path):
    f = TopicFacade(tmp_path / "w.db")
    enqueue(f, "unknown", {})
    r = OutboxWorker(f.store, f).run_once()
    assert r["processed"] == 0 and r["retrying"] == 1
    assert (
        f.store.conn.execute("SELECT status FROM mp_outbox WHERE id='job'").fetchone()[
            0
        ]
        == "pending"
    )
    f.store.close()


def test_forget_worker_cleans_blocked_evidence(tmp_path):
    f = TopicFacade(tmp_path / "w.db")
    r = f.ingest({"content": "需要清理的内容"})
    f.governance.create_tombstone(
        target_type="event", target_id=r["event_id"], scope={"user_id": "default"}
    )
    assert f.search("清理")["results"] == []
    assert OutboxWorker(f.store, f).run_once()["processed"] == 1
    assert f.store.get_event(r["event_id"]).content == "[FORGOTTEN]"
    f.store.close()
