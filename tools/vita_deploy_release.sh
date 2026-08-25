#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
"${ROOT}/tools/vita_require_supervised_hardware_run.sh"

VDB_ROOT="${VDB_ROOT:-$HOME/projects/VitaDevBridge}"
VDB_CONFIG="${VDB_CONFIG:-}"
TITLE_ID="VITAKRT64"
REMOTE_APP="ux0:/app/$TITLE_ID"
REMOTE_DATA="ux0:/data/vitakart64"
PUSH_ARCHIVE="${VITAKART_PUSH_ARCHIVE:-0}"
VERIFY_DEPLOY="${VITAKART_VERIFY_DEPLOY:-1}"
VERIFY_STOPPED="${VITAKART_VERIFY_STOPPED:-1}"

required_files=(
    "$ROOT/eboot.bin"
    "$ROOT/vita-kart-64.vpk"
    "$ROOT/assets/vita/loading.png"
    "$ROOT/assets/vita/shader-manifest.txt"
    "$ROOT/assets/vita/texture-pairs.manifest"
    "$ROOT/livearea-indexed/startup.png"
)

for file in "${required_files[@]}"; do
    if [[ ! -f "$file" ]]; then
        printf 'Missing release artifact: %s\n' "$file" >&2
        exit 1
    fi
done

if [[ "$PUSH_ARCHIVE" == "1" && ! -f "$ROOT/mk64-vita.o2r" ]]; then
    printf 'Missing release artifact: %s\n' "$ROOT/mk64-vita.o2r" >&2
    exit 1
fi

export PYTHONPATH="$VDB_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
cd "$VDB_ROOT"

vdb() {
    local args=()
    if [[ -n "$VDB_CONFIG" ]]; then
        args+=(--config "$VDB_CONFIG")
    fi
    python3 -m vitadevbridge "${args[@]}" --transport network --json "$@"
}

local_sha256() {
    sha256sum "$1" | awk '{print $1}'
}

remote_sha256() {
    vdb fs hash "$1" | python3 -c 'import json,sys; data=json.load(sys.stdin); print(data.get("sha256", ""))'
}

app_running() {
    vdb app status "$TITLE_ID" | python3 -c 'import json,sys; data=json.load(sys.stdin); print("1" if data.get("running") else "0")'
}

stop_app() {
    vdb app kill "$TITLE_ID" --wait-exit --timeout 5 >/dev/null 2>&1 || \
        vdb app kill "$TITLE_ID" >/dev/null 2>&1 || true
}

verify_stopped() {
    if [[ "$VERIFY_STOPPED" != "1" ]]; then
        return
    fi

    if [[ "$(app_running)" != "0" ]]; then
        printf '%s is still running after deploy; refusing to finish as install-stopped.\n' "$TITLE_ID" >&2
        exit 1
    fi
}

push_file() {
    local local_path="$1"
    local remote_path="$2"
    vdb fs push "$local_path" "$remote_path"
    if [[ "$VERIFY_DEPLOY" == "1" ]]; then
        local expected
        local observed
        expected="$(local_sha256 "$local_path")"
        observed="$(remote_sha256 "$remote_path")"
        if [[ "$observed" != "$expected" ]]; then
            printf 'Deploy verification failed for %s -> %s\n' "$local_path" "$remote_path" >&2
            printf 'expected %s observed %s\n' "$expected" "$observed" >&2
            exit 1
        fi
    fi
}

stop_app
push_file "$ROOT/assets/vita/loading.png" "$REMOTE_APP/loading.png"
push_file "$ROOT/assets/vita/shader-manifest.txt" "$REMOTE_APP/shader-manifest.txt"
push_file "$ROOT/assets/vita/texture-pairs.manifest" "$REMOTE_APP/texture-pairs.manifest"
push_file "$ROOT/livearea-indexed/startup.png" "$REMOTE_APP/sce_sys/livearea/contents/startup.png"
if [[ "$PUSH_ARCHIVE" == "1" ]]; then
    push_file "$ROOT/mk64-vita.o2r" "$REMOTE_DATA/mk64.o2r"
fi
push_file "$ROOT/eboot.bin" "$REMOTE_APP/eboot.bin"
push_file "$ROOT/vita-kart-64.vpk" "$REMOTE_DATA/vita-kart-64.vpk"
if [[ "${VITAKART_LAUNCH_AFTER_DEPLOY:-0}" == "1" ]]; then
    vdb app launch "$TITLE_ID"
else
    stop_app
    verify_stopped
fi
