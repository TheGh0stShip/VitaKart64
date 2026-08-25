#!/usr/bin/env python3
"""Collect Vita Kart runtime cache evidence from VitaDevBridge.

Run after a supervised hardware session. This pulls runtime shader and texture
miss files into `runtime-cache/<timestamp>/`. Promotion into packaged seed
manifests is explicit so raw supervised evidence can be reviewed first.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_VDB_ROOT = Path("$HOME/projects/VitaDevBridge")
DEFAULT_CONFIG = DEFAULT_VDB_ROOT / ".vitadevbridge/ps-vita-365-enso-vdb1-paired-full-storage.toml"
REMOTE_FILES = {
    "shader-manifest.txt": "ux0:data/vitakart64/shader-manifest.txt",
    "shader-warmup-summary.txt": "ux0:data/vitakart64/shader-warmup-summary.txt",
    "texture-misses.log": "ux0:data/vitakart64/texture-misses.log",
    "texture-pairs.manifest": "ux0:data/vitakart64/texture-pairs.manifest",
    "preload-summary.txt": "ux0:data/vitakart64/preload-summary.txt",
    "preload-reentry.txt": "ux0:data/vitakart64/preload-reentry.txt",
    "preload-ready.marker": "ux0:data/vitakart64/preload-ready.marker",
    "frame-hitches.log": "ux0:data/vitakart64/frame-hitches.log",
}


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


def try_pull(vdb_root: Path, config: Path, remote: str, local: Path) -> bool:
    try:
        run_vdb(vdb_root, config, ["fs", "pull", remote, str(local)])
        return True
    except RuntimeError as error:
        print(f"skip {remote}: {error}", file=sys.stderr)
        return False


def run_tool(root: Path, tool: str, *args: str) -> None:
    subprocess.run([sys.executable, str(root / "tools" / tool), *args], cwd=root, check=True)


def refresh_latest_cache(root: Path, output_dir: Path, pulled: dict[str, Path]) -> None:
    latest_dir = root / "runtime-cache" / "latest"
    latest_dir.mkdir(parents=True, exist_ok=True)
    if output_dir.resolve() == latest_dir.resolve():
        (latest_dir / "source.json").write_text(
            json.dumps({"source_dir": str(output_dir), "files": sorted(pulled)}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return

    for name in list(REMOTE_FILES) + ["source.json"]:
        existing = latest_dir / name
        if existing.is_file() or existing.is_symlink():
            existing.unlink()

    for name, local in pulled.items():
        if local.is_file():
            shutil.copy2(local, latest_dir / name)

    (latest_dir / "source.json").write_text(
        json.dumps({"source_dir": str(output_dir), "files": sorted(pulled)}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vdb-root", type=Path, default=Path(os.environ.get("VDB_ROOT", DEFAULT_VDB_ROOT)))
    parser.add_argument("--config", type=Path, default=Path(os.environ.get("VDB_CONFIG", DEFAULT_CONFIG)))
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--merge", action="store_true", help="also update packaged seed manifests after pulling files")
    parser.add_argument("--no-merge", action="store_true", help="deprecated compatibility flag; collection is no-merge by default")
    args = parser.parse_args()

    root = project_root()
    require_supervised_hardware_run(root)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    output_dir = args.output_dir if args.output_dir is not None else root / "runtime-cache" / stamp
    output_dir.mkdir(parents=True, exist_ok=True)

    pulled: dict[str, Path] = {}
    for name, remote in REMOTE_FILES.items():
        local = output_dir / name
        if try_pull(args.vdb_root, args.config, remote, local):
            pulled[name] = local

    if args.merge and not args.no_merge:
        run_tool(root, "vita_promote_runtime_cache.py", "--cache-dir", str(output_dir))

    refresh_latest_cache(root, output_dir, pulled)
    print(output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
