#!/usr/bin/env bash
# Build a standalone desktop application with its Python runtime and FP32 model.
set -Eeuo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
target="${1:-dir}"
python_command="${MEMPULSE_BUILD_PYTHON:-python3}"
"$python_command" -c 'import sys; sys.exit("Python >= 3.10 required; set MEMPULSE_BUILD_PYTHON") if sys.version_info < (3, 10) else None'
"$python_command" "$root/scripts/verify_models.py"
if [[ "$(uname -s)" == Linux ]]; then
  bash "$root/OpenCode/deploy/kylin/install-deps.sh"
  exec bash "$root/OpenCode/deploy/kylin/build.sh" "$target"
fi
if [[ "$(uname -s)" != Darwin || "$(uname -m)" != arm64 ]]; then
  echo 'This build entry supports Apple Silicon macOS and native Linux x86_64/ARM64.' >&2
  exit 2
fi
case "$target" in dir|dmg) ;; *) echo 'macOS target must be dir or dmg' >&2; exit 2 ;; esac
developer_dir="$(xcode-select -p)"
if [[ -d "$developer_dir/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk" ]]; then
  export SDKROOT="${SDKROOT:-$developer_dir/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk}"
fi
export CC="${CC:-$(xcrun --find clang)}"
export CXX="${CXX:-$(xcrun --find clang++)}"
export npm_config_python="$python_command"
command -v node >/dev/null
command -v bun >/dev/null
mkdir -p "$root/build-logs"
if [[ ! -x "$root/MemPulse/.venv/bin/python" ]]; then
  "$python_command" -m venv "$root/MemPulse/.venv"
fi
cd "$root/MemPulse"
.venv/bin/python -c 'import sys; assert sys.version_info >= (3, 10), "Recreate .venv with Python >= 3.10"'
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install '.[onnx,test]' 'pyinstaller>=6.10,<7'
.venv/bin/python -m pip freeze > "$root/build-logs/python-resolved.txt"
MEMPULSE_TEST_MODEL="$root/微调模型/revision4-model-bundle" .venv/bin/python -m pytest -q --strict-markers -m 'not standalone_webui'
.venv/bin/python scripts/build_desktop_sidecar.py --with-onnx
cd "$root/OpenCode"
HUSKY=0 bun install --frozen-lockfile
export OPENCODE_CHANNEL=prod
export OPENCODE_VERSION=1.18.30-mempulse.20260915.1
export MEMPULSE_STANDALONE=1
export MODELS_DEV_API_JSON="$root/OpenCode/deploy/kylin/assets/models.dev.json"
export CSC_IDENTITY_AUTO_DISCOVERY=false
cd packages/desktop
bun typecheck
bun ./scripts/prebuild.ts
node ./node_modules/.bin/electron-vite build
if [[ "$target" == dir ]]; then
  node ./node_modules/.bin/electron-builder --config electron-builder.mempulse-mac.config.ts --mac --arm64 --dir --publish never
else
  node ./node_modules/.bin/electron-builder --config electron-builder.mempulse-mac.config.ts --mac dmg --arm64 --publish never
fi
"$root/MemPulse/.venv/bin/python" "$root/OpenCode/deploy/kylin/smoke.py" \
  --service "$PWD/dist/mac-arm64/MemPulse Code.app/Contents/Resources/mempulse/mempulse-service" \
  --bundled-model --output "$root/build-logs/packaged-memory-smoke.json"
echo "Build output: $PWD/dist"
