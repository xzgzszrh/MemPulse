"""Small reproducible local acceptance run. Not the competition benchmark."""

import json
import platform
import statistics
import tempfile
import time
from pathlib import Path
from mempulse.service import TopicFacade


def verify(output):
    checks = {}
    latency = []
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "verify.db"
        f = TopicFacade(path)
        a = f.ingest(
            {
                "event_id": "a",
                "content": "甲客户交付报告",
                "metadata": {
                    "force_new": True,
                    "input_files": ["res:a"],
                    "pending_steps": ["复核"],
                },
                "person_refs": ["self", "张三"],
                "resource_ids": ["res:a"],
            }
        )
        b = f.ingest(
            {
                "event_id": "b",
                "content": "乙客户交付报告",
                "metadata": {"force_new": True},
                "resource_ids": ["res:b"],
            }
        )
        checks["distinct_topics"] = a["topic_id"] != b["topic_id"]
        checks["idempotent"] = f.ingest({"event_id": "a", "content": "甲客户交付报告"})[
            "duplicate"
        ]
        fall = f.ingest(
            {
                "event_id": "fall",
                "content": "主工具失败，回退备用工具",
                "topic_hint": a["topic_id"],
                "is_fallback": True,
            }
        )
        pref = f.update_preference(
            {
                "key": "tool",
                "value": "backup",
                "scope_type": "topic",
                "scope_id": a["topic_id"],
                "evidence_event_id": "fall",
            }
        )
        checks["fallback_not_promoted"] = not pref["promoted"]
        v2 = f.knowledge(
            {
                "key": "template_version",
                "value": "V2",
                "scope_id": a["topic_id"],
                "valid_from": "2026-01-01T00:00:00+00:00",
                "evidence_event_id": "a",
            }
        )
        f.knowledge(
            {
                "key": "template_version",
                "value": "V3",
                "scope_id": a["topic_id"],
                "valid_from": "2026-02-01T00:00:00+00:00",
                "supersedes": v2["id"],
                "evidence_event_id": "a",
            }
        )
        f.checkpoint(a["topic_id"])
        f.store.close()
        f = TopicFacade(path)
        pack = f.restore(a["topic_id"])
        checks["restart_resume"] = pack["checkpoint"]["found"] and all(
            e["event_id"] != "b" for e in pack["events"]
        )
        checks["current_template"] = (
            next(x for x in pack["fields"] if x["name"] == "template_version")["value"]
            == "V3"
        )
        checks["joint_participation"] = (
            f.query_relations("self", "张三")["results"][0]["event_id"] == "a"
        )
        for _ in range(100):
            start = time.perf_counter()
            f.search("甲客户")
            latency.append((time.perf_counter() - start) * 1000)
        f.forget("event", "b")
        checks["forget_clean"] = all(
            e["event_id"] != "b" and "乙客户" not in e["content"]
            for e in f.search("乙客户")["results"]
        ) and all(t["topic_id"] != b["topic_id"] for t in f.list_topics()["topics"])
        f.store.close()
    ordered = sorted(latency)
    report = {
        "checks": checks,
        "passed": all(checks.values()),
        "environment": {
            "os": platform.system(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "latency_ms": {
            "p50": statistics.median(ordered),
            "p95": ordered[94],
            "max": max(ordered),
            "queries": len(ordered),
        },
        "workload": "2 synthetic topics / 3 events",
        "embedding_backend": "unloaded",
        "sdk_tested": False,
        "benchmark_claim": False,
    }
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    return report


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--output", default="reports/verification.json")
    a = p.parse_args()
    r = verify(a.output)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    raise SystemExit(0 if r["passed"] else 1)
