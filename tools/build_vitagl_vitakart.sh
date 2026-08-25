#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
commit="3d035da150549cb38a83811f75856a121754cd5d"
work="$(mktemp -d "${TMPDIR:-/tmp}/vitagl-vk64.XXXXXX")"
trap 'rm -rf "$work"' EXIT
export PATH="/usr/local/vitasdk/bin:$PATH"

curl -fsSL "https://github.com/Rinnegatamante/vitaGL/archive/${commit}.tar.gz" -o "$work/vitagl.tar.gz"
tar -xzf "$work/vitagl.tar.gz" -C "$work"
source_dir="$work/vitaGL-${commit}"
patch -d "$source_dir" -p1 < "$project_root/vendor/vitagl/vitakart-texture-slots.patch"

make -C "$source_dir" -j"${JOBS:-$(nproc)}" \
    HAVE_SHADER_CACHE=1 \
    NO_DEBUG=1 \
    USE_SCRATCH_MEMORY=1 \
    SAMPLERS_SPEEDHACK=1 \
    NO_SPLASHSCREEN=1

archive="$(find "$source_dir" -type f \( -name 'libvitaGL.a' -o -name 'libvitagl.a' \) -print -quit)"
if [[ -z "$archive" ]]; then
    printf 'vitaGL archive was not produced\n' >&2
    exit 1
fi

cp "$archive" "$project_root/vendor/vitagl/libvitagl.a.tmp"
mv "$project_root/vendor/vitagl/libvitagl.a.tmp" "$project_root/vendor/vitagl/libvitagl.a"
printf 'Built Vita Kart 64 vitaGL %s with 32768 texture slots\n' "$commit"
