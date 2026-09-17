#!/usr/bin/env python3
"""Read-only checks for the native Kylin build environment."""
import argparse
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--target', choices=('dir', 'AppImage', 'deb', 'rpm'), default='dir')
args = parser.parse_args()
root = Path(__file__).resolve().parents[3]
errors = []
report = {'system': platform.system(), 'machine': platform.machine(), 'kernel': platform.release(),
          'libc': platform.libc_ver(), 'python': sys.version.split()[0], 'tools': {}}
release = Path('/etc/os-release')
if release.exists():
    report['os_release'] = release.read_text()
if platform.system() != 'Linux':
    errors.append('Run the build on the target Linux machine, not macOS/Windows.')
if platform.machine().lower() not in ('x86_64', 'amd64', 'aarch64', 'arm64'):
    errors.append('This bundle supports native x86_64/aarch64 builds; other ISAs need a separate port.')
if sys.version_info < (3, 10):
    errors.append('Python >= 3.10 is required; Python 3.11/3.12 is recommended for Linux wheels.')
libc, version = platform.libc_ver()
if platform.system() == 'Linux' and (libc != 'glibc' or tuple(map(int, version.split('.')[:2] or ['0'])) < (2, 28)):
    errors.append('The selected Node 24 toolchain needs glibc >= 2.28. Do not replace the system glibc in place.')
for tool, arguments in [('node', ['--version']), ('bun', ['--version']), ('git', ['--version']),
                        ('cc', ['--version']), ('make', ['--version']), ('unzip', ['-v'])]:
    command = shutil.which(tool)
    if command is None:
        errors.append(f'Missing build tool: {tool}')
        continue
    result = subprocess.run([command, *arguments], capture_output=True, text=True, timeout=15)
    report['tools'][tool] = {'path': command, 'version': result.stdout.splitlines()[:1], 'exit_code': result.returncode}
    if result.returncode:
        errors.append(f'{tool} could not run; inspect ABI/architecture and its installation.')
    if tool == 'node' and result.returncode == 0 and int(result.stdout.strip().lstrip('v').split('.')[0]) != 24:
        errors.append('Use Node 24 for the supplied build workflow.')
    if tool == 'bun' and result.returncode == 0:
        bun_version = tuple(int(part) for part in result.stdout.strip().split('-')[0].split('.')[:3])
        if bun_version < (1, 3, 14) or bun_version >= (2, 0, 0):
            errors.append('Use Bun ^1.3.14, matching the project build-script constraint; this handoff was checked with 1.4.2.')
model = root / '微调模型/revision4-model-bundle/encoder/model-fp32.onnx'
report['model_present'] = model.is_file()
if not model.is_file():
    errors.append('Missing FP32 model asset; check extraction and SHA256SUMS.')
report['free_gib'] = round(shutil.disk_usage(root).free / 1024**3, 1)
if args.target == 'deb' and shutil.which('dpkg-deb') is None:
    errors.append('DEB requires dpkg-deb. Confirm this is a Debian-package Kylin desktop; RPM/openEuler systems need a different installer target.')
if report['free_gib'] < 15:
    errors.append('At least 15 GiB free space is required for dependencies, native compilation and packaging.')
report['target'] = args.target
report['errors'] = errors
report['ok'] = not errors
print(json.dumps(report, ensure_ascii=False, indent=2))
raise SystemExit(bool(errors))
