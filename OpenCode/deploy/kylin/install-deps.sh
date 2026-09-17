#!/usr/bin/env bash
set -Eeuo pipefail
trap 'install_exit=$?; printf "Dependency installation failed: exit=%s line=%s command=%s\n" "$install_exit" "$LINENO" "$BASH_COMMAND" >&2; exit "$install_exit"' ERR
bundle_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)"
python_command="${MEMPULSE_BUILD_PYTHON:-python3}"
"$python_command" "$bundle_root/OpenCode/deploy/kylin/preflight.py"
if [[ ! -x "$bundle_root/MemPulse/.venv/bin/python" ]]; then
  "$python_command" -m venv "$bundle_root/MemPulse/.venv"
fi
cd "$bundle_root/MemPulse"
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install '.[onnx,test]' 'pyinstaller>=6.10,<7'
mkdir -p "$bundle_root/build-logs"
.venv/bin/python -m pip freeze > "$bundle_root/build-logs/python-resolved.txt"
cd "$bundle_root/OpenCode"
HUSKY=0 bun install --frozen-lockfile
