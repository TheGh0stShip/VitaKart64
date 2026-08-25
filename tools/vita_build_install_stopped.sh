#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
JOBS="${VITAKART_JOBS:-$(nproc 2>/dev/null || printf '8')}"
export CCACHE_BASEDIR="${CCACHE_BASEDIR:-$ROOT}"
export CCACHE_NOHASHDIR="${CCACHE_NOHASHDIR:-1}"
export VITA_LTO_JOBS="${VITA_LTO_JOBS:-$JOBS}"

"${ROOT}/tools/vita_require_supervised_hardware_run.sh"
export VITAKART_SUPERVISED_HARDWARE_RUN=1
: "${VITAKART_REQUIRE_FULL_CI_COVERAGE:=1}"
: "${VITAKART_TEXTURE_PAIR_LIMIT:=0}"
: "${VITAKART_TEXTURE_MISS_LOG:=0}"
: "${VITAKART_FRAME_HITCH_LOG:=0}"
export VITAKART_REQUIRE_FULL_CI_COVERAGE
export VITAKART_TEXTURE_PAIR_LIMIT
export VITAKART_TEXTURE_MISS_LOG
export VITAKART_FRAME_HITCH_LOG

cd "$ROOT"
if [[ -x "${ROOT}/tools/vita_generate_release_gate_checklist.py" ]]; then
    "${ROOT}/tools/vita_generate_release_gate_checklist.py" --output "${ROOT}/hardware-runs/next-supervised-checklist.md"
fi
if [[ -x "${ROOT}/tools/vita_hash_release_gates.py" ]]; then
    "${ROOT}/tools/vita_hash_release_gates.py" --output "${ROOT}/hardware-runs/release-gate-digest.txt"
fi
if [[ -x "${ROOT}/tools/vita_generate_brand_assets.sh" ]]; then
    "${ROOT}/tools/vita_generate_brand_assets.sh"
fi
if [[ "${VITAKART_SKIP_PREFLIGHT:-0}" != "1" ]]; then
    "${ROOT}/tools/vita_preflight_supervised_build.py" --setup-only
fi
make -f Makefile.vita assets/vita/texture-pairs.manifest
if [[ "${VITAKART_SKIP_PREFLIGHT:-0}" != "1" ]]; then
    "${ROOT}/tools/vita_preflight_supervised_build.py"
fi
if [[ -x "${ROOT}/tools/vita_write_build_input_summary.py" ]]; then
    "${ROOT}/tools/vita_write_build_input_summary.py" --output "${ROOT}/hardware-runs/build-input-summary.md"
fi
make -f Makefile.vita -j"$JOBS" vita-kart-64.vpk
"${ROOT}/tools/vita_write_release_evidence.py"
"${ROOT}/tools/vita_new_hardware_run_report.py"
VITAKART_LAUNCH_AFTER_DEPLOY=0 "${ROOT}/tools/vita_deploy_release.sh"
