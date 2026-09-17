#!/usr/bin/env python3
"""Verify every delivered model file against the original SHA-256 manifest."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / '微调模型/revision4-model-bundle'


def verify():
    manifest = json.loads((MODEL / 'manifest.json').read_text())
    total = 0
    for relative, expected in manifest['files'].items():
        path = MODEL / relative
        if not path.resolve().is_relative_to(MODEL.resolve()):
            raise ValueError(f'Invalid model path: {relative}')
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(block)
        if path.stat().st_size != expected['bytes'] or digest.hexdigest() != expected['sha256']:
            raise ValueError(f'Model checksum mismatch: {relative}')
        total += path.stat().st_size
    print(json.dumps({'model_verified': True, 'files': len(manifest['files']), 'bytes': total}))


if __name__ == '__main__':
    verify()
