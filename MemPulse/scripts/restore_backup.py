"""Restore into a NEW database and replay current tombstones before opening it."""

import argparse
import json
import sqlite3
from pathlib import Path
from mempulse.service import TopicFacade
from scripts.backup import backup


def restore(snapshot, current, output):
    backup(Path(snapshot).resolve(), Path(output).resolve())
    with sqlite3.connect(
        Path(current).resolve().as_uri() + "?mode=ro", uri=True
    ) as conn:
        conn.row_factory = sqlite3.Row
        receipts = [
            dict(r)
            for r in conn.execute("SELECT * FROM mp_tombstones ORDER BY created_at")
        ]
    replayed = 0
    for r in receipts:
        scope = json.loads(r["scope_json"])
        f = TopicFacade(
            output, user_id=scope.get("user_id") or r["requested_by"] or "default"
        )
        try:
            if r["target_type"] == "field":
                event_id = scope["event_id"]
                path = scope["field_path"]
                event = f.store.get_event(event_id)
                if event and event.user_id == f.user_id:
                    try:
                        f.forget_field(event_id, path)
                    except (KeyError, ValueError):
                        f.forget(
                            "event", event_id
                        )  # fail closed if an older schema lacks the field path
            elif r["target_type"] in ("event", "topic"):
                try:
                    f.forget(r["target_type"], r["target_id"])
                except KeyError:
                    pass  # target absent or already hidden
            replayed += 1
        finally:
            f.store.close()
    return {"database": str(output), "tombstones_replayed": replayed}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--snapshot", required=True)
    p.add_argument("--current", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    print(restore(a.snapshot, a.current, a.output))
