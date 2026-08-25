#!/usr/bin/env python3
"""Generate a human-fillable supervised hardware checklist.

This script is intentionally offline-only. It reads the release gate manifest and
prints or writes a Markdown checklist. It does not build, install, launch,
connect to a Vita, collect logs, or validate runtime behavior.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_manifest(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise SystemExit(f"{path} did not contain a JSON object")
    return data


def yn_line(label: str) -> str:
    return f"- [ ] {label} status: ____ notes:"


def render_checklist(manifest: dict[str, Any], manifest_path: Path) -> str:
    now = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    product = manifest.get("product", "Vita Kart 64")
    platform = manifest.get("platform", "PS Vita hardware")
    target = manifest.get("target", {})
    build_policy = manifest.get("required_build_policy", {})
    gates = manifest.get("required_runtime_gates", [])
    diagnostics = manifest.get("diagnostic_order_if_failed", [])

    lines: list[str] = []
    lines.append(f"# {product} supervised release gate checklist")
    lines.append("")
    lines.append(f"- Generated UTC: `{now}`")
    lines.append(f"- Gate manifest: `{manifest_path}`")
    lines.append(f"- Platform: `{platform}`")
    lines.append("- Operator: hardware tester")
    lines.append("- Hardware: PS Vita, not PSTV, not Vita3K")
    lines.append("- Final decision: CANDIDATE / NEEDS FIXES / CRASHED")
    lines.append("")
    lines.append("## Build/install command")
    lines.append("")
    lines.append("```sh")
    lines.append("cd <repo-root>")
    lines.append(str(manifest.get("release_build_command", "VITAKART_SUPERVISED_HARDWARE_RUN=1 tools/vita_prepare_supervised_release.sh")))
    lines.append("```")
    lines.append("")
    lines.append(f"- Launch policy: `{manifest.get('launch_policy', 'install_stopped_then_manual_launch')}`")
    lines.append("")
    lines.append("## Required target")
    lines.append("")
    lines.append(f"- FPS: `{target.get('fps', 60)}`")
    lines.append(f"- ARM MHz: `{target.get('arm_mhz', 500)}`")
    lines.append(f"- BUS MHz: `{target.get('bus_mhz', 222)}`")
    lines.append(f"- GPU MHz: `{target.get('gpu_mhz', 222)}`")
    lines.append(f"- XBAR MHz: `{target.get('xbar_mhz', 166)}`")
    lines.append("")
    lines.append("## Build policy gates")
    lines.append("")
    for key in sorted(build_policy):
        lines.append(yn_line(f"`{key}` expected `{build_policy[key]}`"))
    lines.append("")
    lines.append("## Runtime gates")
    lines.append("")
    lines.append("Fill each `status:` field with exactly one of `PASS`, `FAIL`, or `NOT TESTED`.")
    lines.append("")
    if not isinstance(gates, list):
        raise SystemExit("required_runtime_gates must be a list")
    for gate in gates:
        if not isinstance(gate, dict):
            continue
        gate_id = gate.get("id", "unnamed_gate")
        evidence = gate.get("evidence", "manual_hardware_observation")
        pass_text = gate.get("pass", "")
        lines.append(f"### `{gate_id}`")
        lines.append("")
        lines.append(yn_line(f"gate `{gate_id}`"))
        lines.append(f"- Evidence: `{evidence}`")
        lines.append(f"- Passing condition: {pass_text}")
        lines.append("")
    lines.append("## If anything fails")
    lines.append("")
    if not isinstance(diagnostics, list):
        raise SystemExit("diagnostic_order_if_failed must be a list")
    for index, item in enumerate(diagnostics, 1):
        lines.append(f"{index}. {item}")
    lines.append("")
    lines.append("## Freeform observations")
    lines.append("")
    lines.append("- Loading time:")
    lines.append("- Menu FPS/audio:")
    lines.append("- Race/course tested:")
    lines.append("- First-lap hitches:")
    lines.append("- Post-race scoreboard:")
    lines.append("- Edge artifacts:")
    lines.append("- Image/text quality:")
    lines.append("- Crash dump path if any:")
    lines.append("- Follow-up action:")
    lines.append("")
    return "\n".join(lines)


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
        help="Optional Markdown output path. Defaults to stdout.",
    )
    args = parser.parse_args()

    manifest_path = args.manifest
    if not manifest_path.is_absolute():
        manifest_path = (Path.cwd() / manifest_path).resolve()
    manifest = load_manifest(manifest_path)
    text = render_checklist(manifest, manifest_path)

    if args.output is None:
        print(text)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
