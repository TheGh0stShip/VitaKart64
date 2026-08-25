#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_TXT="$ROOT/vendor/vitagl/BUILD.txt"
VITAGL_ARCHIVE="$ROOT/vendor/vitagl/libvitagl.a"
REQUIRED_VITAGL_FLAGS=(
    HAVE_SHADER_CACHE=1
    NO_DEBUG=1
    USE_SCRATCH_MEMORY=1
    SAMPLERS_SPEEDHACK=1
    NO_SPLASHSCREEN=1
)

"${ROOT}/tools/vita_require_supervised_hardware_run.sh"
export VITAKART_SUPERVISED_HARDWARE_RUN=1
: "${VITAKART_REQUIRE_FULL_CI_COVERAGE:=1}"
: "${VITAKART_TEXTURE_PAIR_LIMIT:=0}"
: "${VITAKART_TEXTURE_MISS_LOG:=0}"
: "${VITAKART_FRAME_HITCH_LOG:=0}"
: "${VITAKART_JOBS:=$(nproc 2>/dev/null || echo 4)}"
export VITAKART_REQUIRE_FULL_CI_COVERAGE
export VITAKART_TEXTURE_PAIR_LIMIT
export VITAKART_TEXTURE_MISS_LOG
export VITAKART_FRAME_HITCH_LOG
export VITAKART_JOBS

CHECKLIST_OUT="${ROOT}/hardware-runs/next-supervised-checklist.md"
if [[ -x "${ROOT}/tools/vita_generate_release_gate_checklist.py" ]]; then
    "${ROOT}/tools/vita_generate_release_gate_checklist.py" --output "$CHECKLIST_OUT" || \
        echo "Warning: failed to generate supervised release checklist at $CHECKLIST_OUT" >&2
fi

GATE_DIGEST_OUT="${ROOT}/hardware-runs/release-gate-digest.txt"
if [[ -x "${ROOT}/tools/vita_hash_release_gates.py" ]]; then
    "${ROOT}/tools/vita_hash_release_gates.py" --output "$GATE_DIGEST_OUT" || \
        echo "Warning: failed to write release gate digest at $GATE_DIGEST_OUT" >&2
fi

if [[ -x "${ROOT}/tools/vita_generate_brand_assets.sh" ]]; then
    "${ROOT}/tools/vita_generate_brand_assets.sh"
fi

vitagl_policy_ok() {
    [[ -f "$VITAGL_ARCHIVE" && -f "$BUILD_TXT" ]] || return 1
    local flag
    for flag in "${REQUIRED_VITAGL_FLAGS[@]}"; do
        grep -q "$flag" "$BUILD_TXT" || return 1
    done
    return 0
}

if ! vitagl_policy_ok; then
    echo "Vendor vitaGL archive does not satisfy Vita Kart 64 release policy; rebuilding it first."
    "${ROOT}/tools/vita_build_vitagl_vendor.sh"
fi

"${ROOT}/tools/vita_build_install_stopped.sh"
