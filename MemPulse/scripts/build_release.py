"""Build the installable Python wheel with the compiled shadcn application."""

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
ui = root / "ui" / "dist"
if not (ui / "index.html").exists():
    raise SystemExit("Run npm ci && npm run build in ui first")
static = root / "src" / "mempulse" / "static"
if static.exists():
    shutil.rmtree(static)
shutil.copytree(ui, static)
subprocess.run(["uv", "build", "--wheel", "--sdist"], cwd=root, check=True)
files = {
    p.name: hashlib.sha256(p.read_bytes()).hexdigest()
    for p in (root / "dist").iterdir()
    if p.is_file() and (p.name.endswith(".whl") or p.name.endswith(".tar.gz"))
}
(root / "dist" / "SHA256.json").write_text(json.dumps(files, indent=2))
print(json.dumps(files, indent=2))
