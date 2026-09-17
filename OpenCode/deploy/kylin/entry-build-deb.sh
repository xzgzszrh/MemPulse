#!/usr/bin/env bash
# Exported at the bundle root as build-deb.sh.
set -Eeuo pipefail
build_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ ! -d "$build_root/OpenCode" ]]; then
  build_root="$(cd -- "$build_root/../../.." && pwd)"
fi
python_command="${MEMPULSE_BUILD_PYTHON:-python3}"
"$python_command" "$build_root/OpenCode/deploy/kylin/verify-bundle.py"
"$python_command" "$build_root/OpenCode/deploy/kylin/preflight.py" --target deb
mkdir -p "$build_root/build-logs"
run_logged() {
  local log_name="$1"
  shift
  set +e
  "$@" 2>&1 | tee "$build_root/build-logs/$log_name.log"
  local run_status="${PIPESTATUS[0]}"
  set -e
  printf '%s exit=%s\n' "$log_name" "$run_status" | tee -a "$build_root/build-logs/exit-codes.log"
  return "$run_status"
}
run_logged install-deps bash "$build_root/OpenCode/deploy/kylin/install-deps.sh"
run_logged build-deb bash "$build_root/OpenCode/deploy/kylin/build.sh" deb
