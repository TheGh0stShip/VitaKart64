#!/usr/bin/env python3
"""Apply a harvested shader-warmup-summary.txt to a hardware run report.

This is a host-side reporting helper. It does not build, deploy, launch,
contact the Vita, or validate runtime behavior.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


FIELD_KEYS = {
    "Shader warmup summary": "schema",
    "Shader manifest entries": "shader_manifest_entries",
    "Shader manifest warmup index": "shader_manifest_warmup_index",
    "Shader manifest capacity": "shader_manifest_capacity",
    "Shader manifest capacity full": "shader_manifest_capacity_full",
    "Shader preset total": "shader_preset_total",
    "Shader preset warmup complete": "shader_preset_warmup_complete",
    "Shader warmup compiled count": "shader_warmup_compiled_count",
    "Shader warmup resident count": "shader_warmup_resident_count",
}


def load_summary(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def apply_summary(report_text: str, summary: dict[str, str]) -> tuple[str, int]:
    replacements = 0
    lines: list[str] = []

    for line in report_text.splitlines():
        replaced = False
        for label, key in FIELD_KEYS.items():
            pattern = rf"^(- {re.escape(label)}:\s*).*$"
            match = re.match(pattern, line)
            if match is None:
                continue
            value = summary.get(key)
            if value is not None:
                lines.append(f"{match.group(1)}{value}")
                replacements += 1
                replaced = True
            break
        if not replaced:
            lines.append(line)

    return "\n".join(lines) + "\n", replacements


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("summary", type=Path, help="harvested shader-warmup-summary.txt")
    parser.add_argument("report", type=Path, help="hardware-runs/vita-run-*.md report to update")
    parser.add_argument("--dry-run", action="store_true", help="print updated report instead of writing it")
    args = parser.parse_args()

    summary = load_summary(args.summary)
    updated, replacements = apply_summary(args.report.read_text(encoding="utf-8", errors="replace"), summary)

    if args.dry_run:
        print(updated, end="")
    else:
        args.report.write_text(updated, encoding="utf-8")
    print(f"updated_shader_warmup_fields={replacements}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
