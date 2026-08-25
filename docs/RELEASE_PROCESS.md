# Release process

Vita Kart 64 public releases are source/tooling releases unless a distributor has confirmed rights to distribute every included asset. Do not attach ROMs, generated `.o2r` archives, VPKs, ELFs, crash dumps, or private Vita data to public releases.

## Release gates

The release gate manifest is `docs/vita-kart-64-release-gates.json`. It encodes the current target:

- locked 60 fps on real PS Vita hardware
- ARM 500 MHz, BUS 222 MHz, GPU 222 MHz, XBAR 166 MHz
- no dynamic performance profiles
- no vitaGL middleware splash
- custom loading screen and brand assets
- shader/audio/resource warmup evidence
- no right/bottom retained-frame artifact

Generate the human checklist:

```sh
tools/vita_generate_release_gate_checklist.py --output hardware-runs/next-supervised-checklist.md
```

## Local hardware candidate build

```sh
VITAKART_SUPERVISED_HARDWARE_RUN=1 tools/vita_prepare_supervised_release.sh
```

That command is intentionally guarded. It may build, deploy, verify hashes, and prepare a real PS Vita hardware run.

## Source release packaging

From a clean public checkout:

```sh
tools/vita_make_source_release.sh v0.1.0
```

The script creates:

- `dist/VitaKart64-<version>-source-tooling.tar.gz`
- `dist/SHA256SUMS`
- `dist/release-manifest.json`

Before publishing, confirm the archive contains no prohibited artifacts:

```sh
find . -type f \( -iname '*.z64' -o -iname '*.n64' -o -iname '*.v64' \
  -o -iname '*.o2r' -o -iname '*.vpk' -o -iname '*.elf' -o -iname '*.velf' \
  -o -iname '*.self' -o -iname '*.psp2dmp' \) -print
```

No output is expected.

## GitHub release command

```sh
git tag -a v0.1.0 -m "Vita Kart 64 source/tooling release"
git push origin main --tags
gh release create v0.1.0 dist/* \
  --repo TheGh0stShip/VitaKart64 \
  --title "Vita Kart 64 v0.1.0 source/tooling" \
  --notes-file RELEASE_NOTES.md
```
