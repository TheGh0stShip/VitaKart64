#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p hardware-runs runtime-cache

./tools/vita_require_supervised_hardware_run.sh "collect and triage Vita Kart 64 supervised runtime evidence"

REPORT="${1:-}"
if [[ -z "$REPORT" ]]; then
    REPORT="$(find hardware-runs -maxdepth 1 -type f -name 'vita-run-*.md' -printf '%T@ %p\n' | sort -nr | sed -n '1s/^[^ ]* //p')"
fi
if [[ -z "$REPORT" ]]; then
    REPORT="$(./tools/vita_new_hardware_run_report.py)"
fi

./tools/vita_collect_runtime_cache.py

if [[ -f runtime-cache/latest/preload-summary.txt ]]; then
    ./tools/vita_apply_preload_summary_to_report.py runtime-cache/latest/preload-summary.txt "$REPORT"
fi

if [[ -f runtime-cache/latest/shader-warmup-summary.txt ]]; then
    ./tools/vita_apply_shader_warmup_summary_to_report.py runtime-cache/latest/shader-warmup-summary.txt "$REPORT"
fi

if [[ "${VITAKART_PULL_LATEST_CRASH:-0}" == "1" ]]; then
    if ! ./tools/vita_pull_latest_crash.py | tee hardware-runs/latest-crash-pull.txt; then
        echo "crash_pull_failed=1" | tee -a hardware-runs/latest-crash-pull.txt
    fi
fi

./tools/vita_promote_runtime_cache.py --dry-run | tee hardware-runs/latest-promotion-preview.txt

if [[ "${VITAKART_PROMOTE_RUNTIME_CACHE:-0}" == "1" ]]; then
    ./tools/vita_promote_runtime_cache.py | tee hardware-runs/latest-promotion.txt
fi

./tools/vita_triage_supervised_run.py | tee hardware-runs/latest-triage.txt

echo "report=$REPORT"
echo "promotion_preview=hardware-runs/latest-promotion-preview.txt"
echo "triage=hardware-runs/latest-triage.txt"
