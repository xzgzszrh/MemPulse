"""Build the native Python sidecar consumed by Electron (and legacy Tauri)."""
import argparse
import importlib.util
import json
import platform
from pathlib import Path
import shutil
import subprocess
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--with-onnx', action='store_true', help='Include FP32 ONNX inference dependencies')
parser.add_argument('--dry-run', action='store_true', help='Print the native target and build command without building')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
machine = platform.machine().lower()
arch = {'arm64': 'aarch64', 'aarch64': 'aarch64', 'amd64': 'x86_64', 'x86_64': 'x86_64'}.get(machine)
system = {'darwin': 'apple-darwin', 'linux': 'unknown-linux-gnu', 'win32': 'pc-windows-msvc'}.get(sys.platform)
if not arch or not system:
    raise SystemExit(f'Unsupported native target: {sys.platform}/{machine}; cross-compiling is not supported')
target = f'{arch}-{system}'
entry = root / 'scripts/desktop_entry.py'
command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile', '--name', 'mempulse-service',
           '--paths', str(root / 'src'), '--distpath', str(root / 'build/sidecar'),
           '--workpath', str(root / 'build/pyinstaller'), '--specpath', str(root / 'build'),
           '--exclude-module', 'torch', '--exclude-module', 'transformers', '--exclude-module', 'hnswlib']
if args.with_onnx:
    for dependency in ('onnxruntime', 'tokenizers', 'numpy'):
        if not args.dry_run and importlib.util.find_spec(dependency) is None:
            raise SystemExit(f'Missing {dependency}; install the project with its onnx extra before building')
        command.extend(['--collect-all', dependency])
else:
    for dependency in ('onnxruntime', 'tokenizers', 'numpy'):
        command.extend(['--exclude-module', dependency])
command.append(str(entry))
suffix = '.exe' if sys.platform == 'win32' else ''
out = root / f'ui/src-tauri/binaries/mempulse-service-{target}{suffix}'
if args.dry_run:
    print(json.dumps({'target': target, 'with_onnx': args.with_onnx, 'output': str(out), 'command': command}, indent=2))
    raise SystemExit(0)
out.parent.mkdir(parents=True, exist_ok=True)
(out.parent.parent / 'host-triple.txt').write_text(target+'\n')
subprocess.run(command, check=True, cwd=root)
shutil.copy2(root / f'build/sidecar/mempulse-service{suffix}', out)
print(out)
