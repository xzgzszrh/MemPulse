"""Install a verified desktop snapshot into an absent data directory, without overwriting data."""
import argparse
import json
import os
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def verify(source, snapshot):
    config = json.loads((source / "model.json").read_text())
    if config.get("precision") != "fp32":
        raise ValueError("expected the approved FP32 configuration")
    with sqlite3.connect((source / "desktop-demo.sqlite3").as_uri() + "?mode=ro", uri=True) as database:
        if database.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("prepared database failed integrity_check")
        if database.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("prepared database contains invalid foreign keys")
        topics = {row[0] for row in database.execute("SELECT id FROM topics")}
        events = {row[0]: json.loads(row[1]) for row in database.execute("SELECT id,payload FROM events")}
        for topic in snapshot["topics"]:
            if topic["topic_id"] not in topics:
                raise ValueError("prepared database is missing an original topic")
        for original in snapshot["events"]:
            current = events.get(original["event_id"])
            if current is None or any(current[key] != original[key] for key in current if key in original):
                raise ValueError("prepared database does not preserve an original event payload")
        if len(topics) < 44 or len(events) < 179:
            raise ValueError("prepared database is missing enrichment data")
        vectors = database.execute("SELECT COUNT(*) FROM topic_vectors WHERE model_revision LIKE 'tide:fp32:%'").fetchone()[0]
        if vectors != len(topics):
            raise ValueError("some prepared topics lack FP32 vectors")
    return {"topics": len(topics), "events": len(events), "fp32_vectors": vectors,
            "original_topics_preserved": len(snapshot["topics"]), "original_events_preserved": len(snapshot["events"]),
            "original_event_payloads_match": True, "integrity_check": "ok"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    source = Path(args.source).resolve()
    target = Path(args.target).resolve()
    raw = json.loads(Path(args.snapshot).read_text())
    snapshot = raw.get("data", raw)
    report = {"checked_at": datetime.now(timezone.utc).isoformat(), "source": str(source),
              "target": str(target), "verification": verify(source, snapshot), "status": "verified"}
    if not args.check_only:
        if target.exists():
            raise FileExistsError("target already exists; existing desktop data will not be overwritten")
        stage = Path(tempfile.mkdtemp(prefix=".mempulse-stage-", dir=target.parent))
        with sqlite3.connect((source / "desktop-demo.sqlite3").as_uri() + "?mode=ro", uri=True) as src:
            with sqlite3.connect(stage / "desktop-demo.sqlite3") as dst:
                src.backup(dst)
        for name in ("model.json", "desktop-settings.json"):
            shutil.copy2(source / name, stage / name)
        for path in stage.iterdir():
            path.chmod(0o600)
        verify(stage, snapshot)
        if target.exists():
            raise FileExistsError("desktop data appeared during preparation; leaving the verified stage untouched")
        os.rename(stage, target)
        report["status"] = "installed"
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
