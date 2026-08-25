#!/usr/bin/env python3
"""Score a filled Vita Kart 64 supervised release checklist.

The checklist is human evidence, not an automated runtime test. This helper only
parses hardware tester's filled Markdown worksheet and summarizes whether the release gates
were marked PASS, FAIL, or NOT TESTED.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


STATUS_RE = re.compile(r"\b(PASS|FAIL|NOT TESTED)\b")
STATUS_FIELD_RE = re.compile(r"\bstatus:\s*(PASS|FAIL|NOT TESTED)\b", re.IGNORECASE)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise SystemExit(f"{path} did not contain a JSON object")
    return data


def parse_status(line: str) -> str | None:
    status_field = STATUS_FIELD_RE.search(line)
    if status_field:
        return status_field.group(1).upper()
    matches = STATUS_RE.findall(line)
    if not matches:
        return None
    unique = set(matches)
    if {"PASS", "FAIL", "NOT TESTED"}.issubset(unique):
        return None
    if "FAIL" in unique:
        return "FAIL"
    if "NOT TESTED" in unique:
        return "NOT TESTED"
    if "PASS" in unique:
        return "PASS"
    return None


def find_status(lines: list[str], label: str) -> str:
    needle = f"`{label}`"
    for line in lines:
        if needle in line:
            status = parse_status(line)
            if status:
                return status
    return "NOT TESTED"


def final_decision(lines: list[str]) -> str:
    for line in lines:
        if line.startswith("- Final decision:"):
            value = line.split(":", 1)[1].strip()
            if "/" in value:
                return "NOT SET"
            return value or "NOT SET"
    return "NOT SET"


def main() -> int:
    root = repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "checklist",
        type=Path,
        help="Filled Markdown checklist from a supervised hardware run.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=root / "docs" / "vita-kart-64-release-gates.json",
        help="Release gate JSON manifest.",
    )
    args = parser.parse_args()

    manifest_path = args.manifest
    if not manifest_path.is_absolute():
        manifest_path = (Path.cwd() / manifest_path).resolve()
    checklist_path = args.checklist
    if not checklist_path.is_absolute():
        checklist_path = (Path.cwd() / checklist_path).resolve()

    manifest = load_json(manifest_path)
    lines = checklist_path.read_text(encoding="utf-8").splitlines()

    build_policy = manifest.get("required_build_policy", {})
    runtime_gates = manifest.get("required_runtime_gates", [])
    if not isinstance(build_policy, dict):
        raise SystemExit("required_build_policy must be a JSON object")
    if not isinstance(runtime_gates, list):
        raise SystemExit("required_runtime_gates must be a JSON array")

    failures: list[str] = []
    print("Vita Kart 64 release-gate checklist score")
    print(f"Checklist: {checklist_path}")
    print(f"Manifest:  {manifest_path}")
    print(f"Decision:  {final_decision(lines)}")
    print("")
    print("Build policy gates:")
    for key in sorted(build_policy):
        status = find_status(lines, key)
        print(f"- {key}: {status}")
        if status != "PASS":
            failures.append(f"build policy {key}: {status}")
    print("")
    print("Runtime gates:")
    for gate in runtime_gates:
        if not isinstance(gate, dict):
            continue
        gate_id = str(gate.get("id", "unnamed_gate"))
        status = find_status(lines, gate_id)
        print(f"- {gate_id}: {status}")
        if status != "PASS":
            failures.append(f"runtime gate {gate_id}: {status}")
    print("")
    if failures:
        print("Result: NEEDS FIXES")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("Result: RELEASE CANDIDATE BY FILLED CHECKLIST")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
