from __future__ import annotations
import importlib.util, os, platform, sqlite3, sys
from pathlib import Path


def inspect(db_path=None):
    db = str(db_path or os.environ.get("MEMPULSE_DB", ".mempulse/memory.sqlite3"))
    checks = {}
    try:
        with sqlite3.connect(db) as c:
            c.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS _mempulse_fts_check USING fts5(value)"
            )
            c.execute("DROP TABLE _mempulse_fts_check")
            checks["sqlite_fts5"] = "ok"
    except Exception as exc:
        checks["sqlite_fts5"] = f"error: {exc}"
    checks.update(
        {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "hnswlib": "installed"
            if importlib.util.find_spec("hnswlib")
            else "missing",
            "onnxruntime": "installed"
            if importlib.util.find_spec("onnxruntime")
            else "missing",
            "model_dir": os.environ.get("MEMPULSE_MODEL_DIR", "not_configured"),
            "kylin_sdk": os.environ.get("MEMPULSE_KYLIN_SDK", "not_configured"),
        }
    )
    checks["ok"] = checks["sqlite_fts5"] == "ok"
    return checks
