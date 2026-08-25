#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

"${ROOT}/tools/vita_generate_loading_art.py" --output "${ROOT}/assets/vita/loading.png"
"${ROOT}/tools/vita_generate_livearea_art.py" --output "${ROOT}/livearea/startup-vk64.png"
"${ROOT}/tools/vita_generate_icon_art.py" --output "${ROOT}/livearea/icon0.png"
"${ROOT}/tools/vita_write_brand_asset_manifest.py" --output "${ROOT}/assets/vita/brand-assets.manifest.json"

cat <<EOF
Generated Vita Kart 64 brand assets:
- ${ROOT}/assets/vita/loading.png
- ${ROOT}/livearea/startup-vk64.png
- ${ROOT}/livearea/icon0.png
- ${ROOT}/assets/vita/brand-assets.manifest.json
EOF
