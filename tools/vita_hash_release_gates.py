#!/usr/bin/env python3
"""Print a stable digest for the Vita Kart 64 release-gate manifest.

This is offline-only. It reads local JSON, canonicalizes it, and emits a SHA-256
digest so supervised run reports can identify exactly which gate definition was
used.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def canonical_digest(path: Path) -> tuple[str, bytes]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest(), canonical


def main() -> int:
    root = repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=root / "docs" / "vita-kart-64-release-gates.json",
        help="Release gate JSON manifest.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional output file for the digest line.",
    )
    args = parser.parse_args()

    manifest = args.manifest
    if not manifest.is_absolute():
        manifest = (Path.cwd() / manifest).resolve()

    digest, _canonical = canonical_digest(manifest)
    line = f"{digest}  {manifest}\n"
    if args.output is None:
        print(line, end="")
    else:
        output = args.output
        if not output.is_absolute():
            output = (Path.cwd() / output).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(line, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
