#!/usr/bin/env python3
"""Export the current source tree without local state or Git history."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
from verify_models import verify, MODEL

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {'.git', 'node_modules', '.venv', '__pycache__', '.pytest_cache', '.ruff_cache',
            'target', 'dist', 'build', 'reports', 'artifacts', '.mempulse', '.DS_Store'}
SUFFIXES = {'.pyc', '.pyo', '.sqlite', '.sqlite3', '.db', '.ses'}


def allowed(path):
    return not (set(path.parts) & EXCLUDED or path.suffix in SUFFIXES
                or any(part.endswith('.egg-info') for part in path.parts)
                or (path.name.startswith('.env') and path.name not in ('.env.example', '.env.sample'))
                or path.as_posix().startswith(('MemPulse/third_party/', 'MemPulse/data/',
                    'MemPulse/runs/', 'MemPulse/src/mempulse/static/', 'MemPulse/ui/src-tauri/binaries/')))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    verify()
    destination = parser.parse_args().output.resolve()
    if destination.exists() or destination.is_relative_to(ROOT):
        parser.error('Output must be a new directory outside the workspace')
    candidates = set()
    for name in ('MemPulse', 'OpenCode'):
        result = subprocess.check_output(['git', '-C', str(ROOT / name), 'ls-files',
                                          '--cached', '--others', '--exclude-standard', '-z'])
        candidates.update(Path(name) / item.decode() for item in result.split(b'\0') if item)
    for name in ('docs', 'scripts', '.github'):
        candidates.update(p.relative_to(ROOT) for p in (ROOT / name).rglob('*') if p.is_file())
    candidates.update(Path(name) for name in ('README.md', 'README.zh-CN.md', 'LICENSE', 'NOTICE', '.gitignore', '.gitattributes'))
    files = []
    for relative in sorted(candidates):
        source = ROOT / relative
        if not allowed(relative) or not source.is_file():
            continue
        if source.is_symlink() and (not source.resolve().is_relative_to(ROOT)
                                    or not allowed(source.resolve().relative_to(ROOT))):
            raise SystemExit(f'External or excluded symlink target: {relative}')
        if source.stat().st_size > 50 * 1024 * 1024:
            raise SystemExit(f'Unexpected large file: {relative}')
        files.append(relative)
    destination.mkdir(parents=True)
    for relative in files:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    shutil.copytree(MODEL, destination / MODEL.relative_to(ROOT),
                    ignore=shutil.ignore_patterns('__pycache__', '.DS_Store', '*.pyc'))
    print(json.dumps({'output': str(destination), 'files': len(files),
                      'git_history_included': False, 'model_weights_included': True}, indent=2))


if __name__ == '__main__':
    main()
