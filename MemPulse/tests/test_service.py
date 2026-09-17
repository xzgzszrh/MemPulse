import json
import tempfile
from pathlib import Path
import pytest
from mempulse.service import TopicFacade
from mempulse.web import create_app
from fastapi.testclient import TestClient


@pytest.fixture
def f(tmp_path):
    service = TopicFacade(tmp_path / "memory.db")
    yield service
    service.store.close()


def event(text="甲客户交付报告", **kwargs):
    return {
        "content": text,
        "topic_title": text,
        "person_refs": ["self@initiator", "zhou@participant"],
        "resource_ids": ["res:input"],
        "metadata": {
            "force_new": True,
            "input_files": ["res:input"],
            "pending_steps": ["复核"],
        },
        **kwargs,
    }


def test_simple_ingest_generates_id_and_persists(f):
    r = f.ingest(event(idempotency_key="run:1"))
    assert r["route"] == "NEW"
    assert r["embedding_backend"] == "unloaded"
    assert not any(t["kind"] == "vector" for t in r["tags"])
    assert f.ingest(event(idempotency_key="run:1"))["duplicate"]
    other = TopicFacade(f.store.path)
    assert other.search("客户交付")["results"][0]["event_id"] == r["event_id"]
    assert other.restore(r["topic_id"])["fields"][0]["status"] == "present"
    other.store.close()


def test_scope_isolation(f):
    r = f.ingest(event())
    other = TopicFacade(f.store.path, user_id="other")
    assert other.search("客户交付")["results"] == []
    with pytest.raises(KeyError):
        other.restore(r["topic_id"])
    other.store.close()


def test_forget_cleans_derived_context_and_search(f):
    r = f.ingest(event("保密信息ZXQ私号"))
    f.checkpoint(r["topic_id"])
    receipt = f.forget("event", r["event_id"])
    assert receipt["status"] == "complete"
    assert f.search("ZXQ")["results"] == []
    assert f.list_topics()["topics"] == []
    assert (
        f.governance.get_checkpoint(user_id="default", topic_id=r["topic_id"])["found"]
        is False
    )
    assert "私号" not in json.dumps(f.restore(r["topic_id"]), ensure_ascii=False)


def test_ingest_rolls_back_topic_if_event_write_fails(f, monkeypatch):
    def fail(*a, **k):
        raise RuntimeError("simulated disk failure")

    monkeypatch.setattr(f.store, "save_event", fail)
    with pytest.raises(RuntimeError):
        f.ingest(event())
    assert f.list_topics()["topics"] == []


def test_explicit_topic_survives_restart_and_event_isolated(f):
    a = f.ingest(event("甲客户报告"))
    b = f.ingest(event("乙客户报告"))
    other = TopicFacade(f.store.path)
    r = other.ingest({"content": "下一步复核", "topic_hint": a["topic_id"]})
    assert r["topic_id"] == a["topic_id"]
    assert b["event_id"] not in [
        x["event_id"] for x in other.restore(a["topic_id"])["events"]
    ]
    other.store.close()


def test_http_roundtrip_and_local_origin(tmp_path):
    with TestClient(create_app(tmp_path / "api.db", serve_ui=False)) as c:
        assert c.get("/health").json()["ok"]
        result = c.post("/api/ingest", json=event()).json()
        assert result["route"] == "NEW"
        assert (
            c.get("/api/restore", params={"topic_id": result["topic_id"]}).status_code
            == 200
        )
        assert (
            c.post(
                "/api/ingest", json=event(), headers={"Origin": "https://example.com"}
            ).status_code
            == 403
        )
        # The Electron backend contract must not depend on a separately built WebUI.
        page = c.get("/")
        assert page.status_code == 200
        assert page.headers["content-type"].startswith("application/json")
        assert page.json()["webui"] == "disabled"


def test_relations_use_same_event_evidence(f):
    r = f.ingest(event())
    rows = f.query_relations("self", "zhou")
    assert rows["complete"]
    assert rows["results"][0]["event_id"] == r["event_id"]


def test_graph_query_does_not_create_an_unrelated_demo_database(tmp_path):
    with TestClient(create_app(tmp_path / 'api.db', serve_ui=False)) as client:
        assert client.get('/api/graph').status_code == 200
        assert client.get('/api/topics').json()['topics'] == []
        assert not (tmp_path / 'desktop-demo.sqlite3').exists()


def test_field_forget_preserves_procedure(f):
    r = f.ingest(
        {
            "content": "电话 13800138000，流程先审核再发布",
            "metadata": {
                "private_phone": "13800138000",
                "procedure": "先审核再发布",
                "force_new": True,
            },
        }
    )
    receipt = f.forget_field(r["event_id"], "metadata.private_phone")
    assert receipt["status"] == "complete"
    pack = f.restore(r["topic_id"])
    assert "13800138000" not in json.dumps(pack)
    assert "先审核再发布" in json.dumps(pack, ensure_ascii=False)


def test_topic_split_merge_and_correction(f):
    a = f.ingest(event())
    second = f.ingest({"content": "第二个执行步骤", "topic_hint": a["topic_id"]})
    b = f.split_topic(a["topic_id"], [second["event_id"]], "分支工作")
    assert len(f.restore(b["topic_id"])["events"]) == 1
    assert len(f.restore(a["topic_id"])["events"]) == 1
    f.merge_topics(b["topic_id"], a["topic_id"])
    assert len(f.restore(a["topic_id"])["events"]) == 2


def test_backup_restore_replays_forgetting(tmp_path):
    from scripts.backup import backup
    from scripts.restore_backup import restore

    f = TopicFacade(tmp_path / "live.db")
    r = f.ingest(event("测试隐私ZXQ"))
    backup(tmp_path / "live.db", tmp_path / "before.db")
    f.forget("event", r["event_id"])
    restore(tmp_path / "before.db", tmp_path / "live.db", tmp_path / "restored.db")
    check = TopicFacade(tmp_path / "restored.db")
    assert check.search("ZXQ")["results"] == []
    f.store.close()
    check.store.close()


def test_strict_gate_keeps_incomplete_topics_out_of_retrieval(tmp_path, monkeypatch):
    monkeypatch.setenv("MEMPULSE_STRICT_TAGS", "1")
    f = TopicFacade(tmp_path / "strict.db")
    f.ingest({"content": "尚无完整标签的草稿"})
    assert f.search("草稿")["results"] == []
    assert f.health()["index_policy"] == "strict"
    f.store.close()
