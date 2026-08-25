#!/usr/bin/env python3
"""Write a manifest for Vita Kart 64 generated brand assets.

This is local-only metadata generation. It does not build, install, launch,
connect to a Vita, harvest caches, pull crashes, or validate runtime behavior.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ASSETS = (
    "assets/vita/loading.png",
    "livearea/startup-vk64.png",
    "livearea/icon0.png",
)

SOURCES = (
    "tools/vita_generate_brand_assets.sh",
    "tools/vita_generate_loading_art.py",
    "tools/vita_generate_livearea_art.py",
    "tools/vita_generate_icon_art.py",
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def record(root: Path, relative: str) -> dict[str, object]:
    path = root / relative
    if not path.exists():
        return {"path": relative, "present": False}
    return {
        "path": relative,
        "present": True,
        "size": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def main() -> int:
    root = repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "assets" / "vita" / "brand-assets.manifest.json",
        help="Output JSON manifest path.",
    )
    args = parser.parse_args()

    output = args.output
    if not output.is_absolute():
        output = (Path.cwd() / output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    manifest = {
        "schema": "vitakart64.brand-assets.v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "assets": [record(root, relative) for relative in ASSETS],
        "sources": [record(root, relative) for relative in SOURCES],
    }
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
