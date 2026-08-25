#!/usr/bin/env bash
set -euo pipefail

VERSION="${1:-}"
if [[ -z "$VERSION" ]]; then
    echo "Usage: tools/vita_make_source_release.sh vX.Y.Z" >&2
    exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NAME="VitaKart64-${VERSION#v}"
DIST="$ROOT/dist"
ARCHIVE="$DIST/${NAME}-source-tooling.tar.gz"
MANIFEST="$DIST/release-manifest.json"
SUMS="$DIST/SHA256SUMS"

cd "$ROOT"
mkdir -p "$DIST"
git archive --format=tar.gz --prefix="$NAME/" -o "$ARCHIVE" HEAD
sha256sum "$ARCHIVE" > "$SUMS"
cat > "$MANIFEST" <<JSON
{
  "name": "Vita Kart 64 source/tooling",
  "version": "$VERSION",
  "archive": "$(basename "$ARCHIVE")",
  "roms_included": false,
  "o2r_included": false,
  "vpk_included": false,
  "requires_user_supplied_rom": true,
  "supported_rom_sha1": "579C48E211AE952530FFC8738709F078D5DD215E"
}
JSON
sha256sum "$MANIFEST" >> "$SUMS"

cat <<OUT
Created:
$ARCHIVE
$MANIFEST
$SUMS
OUT
