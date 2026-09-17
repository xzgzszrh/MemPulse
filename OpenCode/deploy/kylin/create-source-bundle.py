#!/usr/bin/env python3
"""Export committed application sources and the verified model bundle for native Linux builds."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, required=True, help='New, non-existing bundle directory')
parser.add_argument('--runtime-model', action='store_true', help='Ship only FP32 inference assets; omit training weights and INT8')
args = parser.parse_args()
root = Path(__file__).resolve().parents[3]
destination = args.output.resolve()
if destination.exists() or destination.with_suffix('.tar.gz').exists():
    raise SystemExit('Choose a new output path; existing bundles are never replaced')


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def copy(source, relative):
    target = destination / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_symlink():
        link = source.readlink()
        if link.is_absolute() or not source.resolve().is_relative_to(root):
            raise ValueError(f'Non-portable source symlink: {relative}')
        target.symlink_to(link)
    else:
        shutil.copy2(source, target)


sources = {}
for name in ('OpenCode', 'MemPulse'):
    repository = root / name
    subprocess.run(['git', 'diff', '--quiet', 'HEAD'], cwd=repository, check=True)
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repository, text=True).strip()
    files = subprocess.check_output(['git', 'ls-files', '-z'], cwd=repository).decode().split('\0')
    included = 0
    for item in filter(None, files):
        relative = Path(item)
        if relative.parts[0] in ('artifacts', 'ui') or any(part in ('node_modules', '.git', '.venv') for part in relative.parts):
            continue
        if name == 'MemPulse' and relative.parts[:3] == ('src', 'mempulse', 'static'):
            continue
        if relative.name in ('.env', '.env.local', '.DS_Store'):
            continue
        source = repository / relative
        if not source.is_file() and not source.is_symlink():
            raise ValueError(f'Missing committed file: {name}/{item}')
        copy(source, Path(name) / relative)
        included += 1
    sources[name] = {'commit': commit, 'files': included}

model_relative = Path('微调模型/revision4-model-bundle')
model = root / model_relative
manifest = json.loads((model / 'manifest.json').read_text())
for relative, expected in manifest['files'].items():
    source = model / relative
    if source.stat().st_size != expected['bytes'] or digest(source) != expected['sha256']:
        raise ValueError(f'Model manifest mismatch: {relative}')
for source in sorted(model.rglob('*')):
    if source.is_file() and source.name != '.DS_Store' and '__pycache__' not in source.parts:
        if args.runtime_model and source != model / 'manifest.json' and (
            source.relative_to(model).parts[0] != 'encoder' or source.name == 'model-int8-mixed.onnx'
        ):
            continue
        copy(source, model_relative / source.relative_to(model))

copy(root / 'OpenCode/deploy/kylin/README.md', Path('README_麒麟编译.md'))
copy(root / 'OpenCode/deploy/kylin/CODEX_HANDOFF.md', Path('CODEX_HANDOFF.md'))
copy(root / 'OpenCode/deploy/kylin/entry-build-deb.sh', Path('build-deb.sh'))
metadata = {'created_at': datetime.now(timezone.utc).isoformat(), 'type': 'native-linux-source-build-handoff',
            'sources': sources, 'model': {'path': str(model_relative), 'manifest_sha256': digest(model / 'manifest.json'),
                                        'default_precision': 'fp32', 'full_delivery_bundle': not args.runtime_model,
                                        'included_assets': [p.relative_to(destination / model_relative).as_posix() for p in sorted((destination / model_relative).rglob('*')) if p.is_file()]},
            'user_confirmed_target': 'x86_64', 'supported_native_architectures': ['x86_64', 'aarch64'], 'linux_native_build_verified': False,
            'includes_private_client_database': False, 'includes_provider_credentials': False,
            'excluded': ['.git metadata', 'node_modules', '.venv', 'macOS binaries', 'standalone MemPulse/ui and generated static assets',
                         'OpenCode/artifacts', 'client user data and provider settings'],
            'client': 'OpenCode/packages/desktop Electron with OpenCode/packages/app frontend',
            'backend_test_command': "pytest -q --strict-markers -m 'not standalone_webui'",
            'network_required_for_dependencies': True}
(destination / 'SOURCE_MANIFEST.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
files = sorted(path for path in destination.rglob('*') if path.is_file())
with (destination / 'SHA256SUMS').open('w') as stream:
    for path in files:
        stream.write(f'{digest(path)}  {path.relative_to(destination).as_posix()}\n')

subprocess.run([sys.executable, str(destination/'OpenCode/deploy/kylin/verify-bundle.py')], check=True)


def portable(info):
    info.uid = info.gid = 0
    info.uname = info.gname = ''
    return info


archive = destination.with_suffix('.tar.gz')
with tarfile.open(archive, 'w:gz', compresslevel=5, format=tarfile.PAX_FORMAT) as output:
    output.add(destination, arcname=destination.name, filter=portable)
archive_hash = digest(archive)
archive.with_name(archive.name + '.sha256').write_text(f'{archive_hash}  {archive.name}\n')
print(json.dumps({'archive': str(archive), 'bytes': archive.stat().st_size, 'sha256': archive_hash,
                  'files': len(files), 'sources': sources}, ensure_ascii=False, indent=2))
