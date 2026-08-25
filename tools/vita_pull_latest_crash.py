#!/usr/bin/env python3
"""Pull the newest Vita crash dump for Vita Kart 64.

This avoids manually typing psp2core/psp2dmp names after each crash. It uses
VitaDevBridge `fs list` plus `fs pull`, scans common Vita crash locations, and
copies the newest matching dump into `crashes/`.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

DEFAULT_VDB_ROOT = Path("$HOME/projects/VitaDevBridge")
DEFAULT_CONFIG = DEFAULT_VDB_ROOT / ".vitadevbridge/ps-vita-365-enso-vdb1-paired-full-storage.toml"
DEFAULT_ROOTS = (
    "ux0:data",
    "ux0:/data",
    "ux0:app/VITAKRT64",
    "ux0:/app/VITAKRT64",
    "ux0:app",
    "ux0:/app",
)
CRASH_RE = re.compile(r"(?:psp2core-)?(?P<stamp>\d+)-0x[0-9a-fA-F]+-eboot\.bin\.psp2dmp$")


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def require_supervised_hardware_run(root: Path) -> None:
    if os.environ.get("VITAKART_SUPERVISED_HARDWARE_RUN", "0") == "1":
        return
    guard = root / "tools/vita_require_supervised_hardware_run.sh"
    subprocess.run([str(guard)], cwd=root, check=True)


def run_vdb(vdb_root: Path, config: Path, args: list[str]) -> Any:
    env = os.environ.copy()
    src = str(vdb_root / "src")
    env["PYTHONPATH"] = src + ((":" + env["PYTHONPATH"]) if env.get("PYTHONPATH") else "")
    command = [
        sys.executable,
        "-m",
        "vitadevbridge",
        "--config",
        str(config),
        "--transport",
        "network",
        "--json",
        *args,
    ]
    proc = subprocess.run(command, cwd=vdb_root, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or f"VDB failed: {' '.join(args)}")
    return json.loads(proc.stdout) if proc.stdout.strip() else None


def entry_path(entry: Any) -> str:
    if isinstance(entry, dict):
        value = entry.get("path") or entry.get("remote_path") or entry.get("name")
        return value if isinstance(value, str) else ""
    value = getattr(entry, "path", "")
    return value if isinstance(value, str) else ""


def entry_size(entry: Any) -> int:
    if isinstance(entry, dict):
        value = entry.get("size")
        return value if isinstance(value, int) else 0
    value = getattr(entry, "size", 0)
    return value if isinstance(value, int) else 0


def collect_entries(vdb_root: Path, config: Path, roots: tuple[str, ...]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for root in roots:
        try:
            listing = run_vdb(vdb_root, config, ["fs", "list", root])
        except RuntimeError:
            continue
        entries = listing.get("entries", []) if isinstance(listing, dict) else []
        for entry in entries:
            path = entry_path(entry)
            if path.endswith(".psp2dmp") and CRASH_RE.search(path.rsplit("/", 1)[-1]):
                found.append({"path": path, "size": entry_size(entry)})
    return found


def crash_sort_key(entry: dict[str, Any]) -> tuple[int, int, str]:
    name = entry["path"].rsplit("/", 1)[-1]
    match = CRASH_RE.search(name)
    stamp = int(match.group("stamp")) if match else 0
    return (stamp, int(entry.get("size", 0)), entry["path"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vdb-root", type=Path, default=Path(os.environ.get("VDB_ROOT", DEFAULT_VDB_ROOT)))
    parser.add_argument("--config", type=Path, default=Path(os.environ.get("VDB_CONFIG", DEFAULT_CONFIG)))
    parser.add_argument("--output-dir", type=Path, default=Path("crashes"))
    parser.add_argument("--root", action="append", dest="roots", help="remote root to scan; can be repeated")
    args = parser.parse_args()

    require_supervised_hardware_run(project_root())

    roots = tuple(args.roots) if args.roots else DEFAULT_ROOTS
    entries = collect_entries(args.vdb_root, args.config, roots)
    if not entries:
        print("no Vita Kart crash dumps found", file=sys.stderr)
        return 1

    latest = max(entries, key=crash_sort_key)
    remote = latest["path"]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    local = args.output_dir / remote.rsplit("/", 1)[-1]
    run_vdb(args.vdb_root, args.config, ["fs", "pull", remote, str(local)])
    print(local)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
