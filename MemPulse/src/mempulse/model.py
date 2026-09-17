from __future__ import annotations
import hashlib, json
from pathlib import Path


def register(path, output=None, precision="fp32"):
    from .embeddings import model_assets
    assets = model_assets(path, precision)
    result = {
        "status": "ready_for_runtime_probe",
        "model_dir": str(assets["root"]),
        "model_sha256": assets["hashes"][assets["model"].name],
        "precision": precision,
        "model_revision": assets["revision"],
        "manifest_verified": assets["manifest_verified"],
        "automatic_binding_allowed": assets["automatic_binding_allowed"],
        "missing_files": [],
        "sdk_registration": "not_attempted",
    }
    if output:
        Path(output).write_text(json.dumps(result, ensure_ascii=False, indent=2))
    return result
