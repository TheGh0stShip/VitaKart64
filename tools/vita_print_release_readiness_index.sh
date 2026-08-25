#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cat "$ROOT/docs/vita-kart-64-release-readiness-index.md"
