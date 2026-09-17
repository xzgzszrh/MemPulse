#!/usr/bin/env bash
set -Eeuo pipefail
trap 'build_exit=$?; printf "Build failed: exit=%s line=%s command=%s\n" "$build_exit" "$LINENO" "$BASH_COMMAND" >&2; exit "$build_exit"' ERR
bundle_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)"
target="${1:-deb}"
case "$target" in dir|AppImage|deb|rpm) ;; *) echo 'Usage: build.sh [dir|AppImage|deb|rpm]' >&2; exit 2 ;; esac
python_command="${MEMPULSE_BUILD_PYTHON:-python3}"
"$python_command" "$bundle_root/OpenCode/deploy/kylin/preflight.py" --target "$target"
if [[ ! -x "$bundle_root/MemPulse/.venv/bin/python" ]]; then
  echo 'Run install-deps.sh first.' >&2
  exit 1
fi
mkdir -p "$bundle_root/build-logs"
export OPENCODE_CHANNEL=prod
export OPENCODE_VERSION=1.18.30-mempulse.20260915.2
export MEMPULSE_STANDALONE=1
export MODELS_DEV_API_JSON="${MODELS_DEV_API_JSON:-$bundle_root/OpenCode/deploy/kylin/assets/models.dev.json}"
if [[ ! -s "$MODELS_DEV_API_JSON" ]]; then
  echo 'Missing models.dev snapshot; verify extraction and SHA256SUMS.' >&2
  exit 1
fi
cd "$bundle_root/MemPulse"
PYTHONPATH=src MEMPULSE_TEST_MODEL="$bundle_root/微调模型/revision4-model-bundle" .venv/bin/python -m pytest -q --strict-markers -m 'not standalone_webui'
.venv/bin/python scripts/build_desktop_sidecar.py --with-onnx
cd "$bundle_root/OpenCode/packages/app"
bun typecheck
bun test src/memory/constellation.test.ts
cd "$bundle_root/OpenCode/packages/desktop"
bun typecheck
bun test electron-builder.config.test.ts
bun ./scripts/prebuild.ts
node ./node_modules/.bin/electron-vite build
case "$(uname -m)" in x86_64) arch=x64 ;; aarch64|arm64) arch=arm64 ;; esac
if [[ "$target" == dir ]]; then
  node ./node_modules/.bin/electron-builder --config electron-builder.kylin.config.ts --linux --"$arch" --dir --publish never
else
  node ./node_modules/.bin/electron-builder --config electron-builder.kylin.config.ts --linux "$target" --"$arch" --publish never
fi
unpacked="$PWD/dist/linux-unpacked"
if [[ "$arch" == arm64 ]]; then unpacked="$PWD/dist/linux-arm64-unpacked"; fi
"$bundle_root/MemPulse/.venv/bin/python" "$bundle_root/OpenCode/deploy/kylin/smoke.py" \
  --service "$unpacked/resources/mempulse/mempulse-service" --bundled-model \
  --output "$bundle_root/build-logs/packaged-memory-smoke.json"
printf 'Build output: %s\n' "$PWD/dist"
printf 'Launch: %s/ai.opencode.desktop\n' "$unpacked"
