#!/usr/bin/env python3
"""Verify the exported source closure without installing or starting the client."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

if sys.version_info < (3, 10):
    raise SystemExit('Python >=3.10 required. Use an installed Python 3.11/3.12 and set MEMPULSE_BUILD_PYTHON for build-deb.sh.')

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[3])
args = parser.parse_args()
root = args.root.resolve()
errors = []
count = 0
exported = []

def sha256(path):
    result = hashlib.sha256()
    with path.open('rb') as source:
        for data in iter(lambda: source.read(1024*1024), b''):
            result.update(data)
    return result.hexdigest()

for line in (root/'SHA256SUMS').read_text().splitlines():
    expected, relative = line.split('  ', 1)
    exported.append(relative)
    path = root/relative
    if not path.resolve().is_relative_to(root) or not path.is_file() or sha256(path) != expected:
        errors.append('Missing or modified export: '+relative)
    count += 1

required = [
    'OpenCode/bun.lock', 'OpenCode/package.json',
    'OpenCode/packages/app/src/index.ts', 'OpenCode/packages/app/src/index.css',
    'OpenCode/packages/app/src/memory/views/overview-3d.tsx',
    'OpenCode/packages/desktop/electron-builder.kylin.config.ts',
    'OpenCode/deploy/kylin/assets/models.dev.json',
    'MemPulse/pyproject.toml', 'MemPulse/pytest.ini', 'MemPulse/tests/test_webui.py',
    'MemPulse/src/mempulse/merged_demo.py', 'MemPulse/src/mempulse/realistic_scenarios.py',
    'MemPulse/scripts/build_desktop_sidecar.py',
    '微调模型/revision4-model-bundle/manifest.json',
    '微调模型/revision4-model-bundle/encoder/model-fp32.onnx',
    '微调模型/revision4-model-bundle/encoder/tokenizer.json',
    '微调模型/revision4-model-bundle/encoder/tide_config.json',
]
for relative in required:
    if not (root/relative).is_file(): errors.append('Required build input missing: '+relative)

opencode = root/'OpenCode'
package = json.loads((opencode/'package.json').read_text())
workspaces = package['workspaces']['packages']
local_dependencies = 0
for package_json in {p/'package.json' for pattern in workspaces for p in opencode.glob(pattern) if (p/'package.json').is_file()}:
    value = json.loads(package_json.read_text())
    for section in ('dependencies', 'devDependencies', 'optionalDependencies'):
        for name, version in value.get(section, {}).items():
            if not version.startswith(('file:', 'link:')): continue
            target = (package_json.parent/version.split(':', 1)[1]).resolve()
            local_dependencies += 1
            if not target.is_relative_to(root) or not target.exists():
                errors.append(f'Missing local dependency: {package_json.relative_to(root)} / {name} / {version}')

catalog = json.loads((opencode/'deploy/kylin/assets/models.dev.json').read_text())
if not isinstance(catalog, dict) or not any(isinstance(item, dict) and item.get('models') for item in catalog.values()):
    errors.append('Invalid models.dev snapshot')
build = (opencode/'deploy/kylin/build.sh').read_text()
if "--strict-markers -m 'not standalone_webui'" not in build:
    errors.append('Electron backend test boundary missing')
for forbidden in ('MemPulse/ui', 'MemPulse/src/mempulse/static', 'MemPulse/.venv', 'OpenCode/node_modules'):
    if any(relative == forbidden or relative.startswith(forbidden+'/') for relative in exported):
        errors.append('Unexpected local build residue in export: '+forbidden)

print(json.dumps({'ok': not errors, 'verified_files': count, 'local_file_dependencies': local_dependencies,
                  'standalone_webui_required': False, 'errors': errors}, ensure_ascii=False, indent=2))
raise SystemExit(bool(errors))
