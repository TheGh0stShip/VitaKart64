#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
JOBS="${VITAKART_JOBS:-$(nproc 2>/dev/null || printf '8')}"
VITAGL_REF="${VITAKART_VITAGL_REF:-3d035da150549cb38a83811f75856a121754cd5d}"
VITAGL_SRC="${VITAKART_VITAGL_SRC:-$ROOT/build/vitagl-src}"
VITAGL_FLAGS=(
    HAVE_SHADER_CACHE=1
    NO_DEBUG=1
    USE_SCRATCH_MEMORY=1
    SAMPLERS_SPEEDHACK=1
    NO_SPLASHSCREEN=1
)

"${ROOT}/tools/vita_require_supervised_hardware_run.sh"

mkdir -p "$(dirname "$VITAGL_SRC")"
if [[ ! -d "$VITAGL_SRC/.git" ]]; then
    git clone https://github.com/Rinnegatamante/vitaGL.git "$VITAGL_SRC"
fi

cd "$VITAGL_SRC"
git fetch --tags origin
git checkout "$VITAGL_REF"

if [[ -s "$ROOT/vendor/vitagl/vitakart-texture-slots.patch" ]]; then
    if git apply --check "$ROOT/vendor/vitagl/vitakart-texture-slots.patch"; then
        git apply "$ROOT/vendor/vitagl/vitakart-texture-slots.patch"
    elif git apply --reverse --check "$ROOT/vendor/vitagl/vitakart-texture-slots.patch"; then
        echo "Vita Kart vitaGL compatibility patch is already applied."
    else
        echo "Vita Kart vitaGL compatibility patch cannot be applied cleanly." >&2
        exit 1
    fi
fi

make clean >/dev/null 2>&1 || true
make -j"$JOBS" "${VITAGL_FLAGS[@]}"

candidate=""
for path in libvitagl.a libvitaGL.a source/libvitagl.a source/libvitaGL.a; do
    if [[ -f "$path" ]]; then
        candidate="$path"
        break
    fi
done

if [[ -z "$candidate" ]]; then
    echo "Could not find built vitaGL static archive." >&2
    exit 1
fi

mkdir -p "$ROOT/vendor/vitagl"
cp "$candidate" "$ROOT/vendor/vitagl/libvitagl.a"
cat > "$ROOT/vendor/vitagl/BUILD.txt" <<EOF
VitaGL upstream: https://github.com/Rinnegatamante/vitaGL
Commit: $VITAGL_REF
Target: Vita Kart 64 (hard-float)
Flags: ${VITAGL_FLAGS[*]}
Compatibility patch: unused shark_set_shader_association_path hook disabled for installed VitaShaRK ABI.
Built: $(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF

printf 'Updated %s\n' "$ROOT/vendor/vitagl/libvitagl.a"
