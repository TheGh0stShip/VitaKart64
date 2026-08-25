# Vita Kart 64

Vita Kart 64 is a PS Vita-focused source/tooling port of the Spaghetti Kart / Mario Kart 64 decompilation runtime. The target is PS Vita hardware at a locked 60 fps profile with max-performance clocks, deterministic resource loading, shader/resource warmup, and a Vita-specific install/test workflow.

This repository is source and tooling only. It intentionally does not ship a ROM, Nintendo assets, generated `.o2r` archives, `.vpk` packages, crash dumps, or private hardware-run data.

## Current Vita target

- Hardware: real PS Vita, not PSTV, not Vita3K as the final validation target.
- Title ID: `VITAKRT64`.
- Product name: `Vita Kart 64`.
- Performance policy: always max performance, no separate performance profiles.
- Expected OC profile: ARM `500 MHz`, BUS `222 MHz`, GPU `222 MHz`, XBAR `166 MHz`.
- Render policy: fixed `1/2` internal render scale, with presentation clamps for right/bottom edge artifacts.
- Runtime polish: custom loading art path, no vitaGL splash, shader manifest warmup, CI/TLUT preload manifesting, audio warmup evidence, and supervised hardware release gates.

## Legal boundary

You need a legally obtained US Mario Kart 64 ROM dump. The expected SHA-1 for the supported US ROM is:

```text
579C48E211AE952530FFC8738709F078D5DD215E
```

Do not commit or upload ROMs, generated `.o2r` files, `.vpk` files, crash dumps, or private hardware data. See `docs/LEGAL_AND_ASSETS.md`.

## Quick setup

```sh
git clone https://github.com/TheGh0stShip/VitaKart64.git
cd VitaKart64

python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt

export VITASDK=/usr/local/vitasdk
export PATH="$VITASDK/bin:$PATH"
```

Install VitaSDK and required Vita packages first. Then build the local vitaGL archive used by this port:

```sh
tools/vita_build_vitagl_vendor.sh
```

Generate local game archives from your own ROM:

```sh
# Generate mk64.o2r with the upstream Spaghetti Kart extraction flow, then place it here.
cp /path/to/mk64.o2r ./mk64.o2r

# Convert the game archive to a deterministic stored-layout Vita archive.
tools/vita_optimize_o2r.py mk64.o2r mk64-vita.o2r

# Generate or copy spaghetti.o2r from the desktop CMake GenerateO2R target.
cmake -S . -B build-cmake -GNinja -DCMAKE_BUILD_TYPE=Release
cmake --build build-cmake --target GenerateO2R
cp build-cmake/spaghetti.o2r ./spaghetti.o2r 2>/dev/null || true
```

Build the VPK locally:

```sh
make -f Makefile.vita -j"$(nproc)" vita-kart-64.vpk
```

See `docs/VITA_SETUP.md` for the full dependency and build flow.

## Hardware install workflow

Manual install is supported through VitaShell. Automated install is supported through VitaDevBridge/VitaCompanion when configured:

```sh
export VDB_ROOT="$HOME/projects/VitaDevBridge"
export VDB_CONFIG="$VDB_ROOT/.vitadevbridge/your-paired-vita.toml"
VITAKART_SUPERVISED_HARDWARE_RUN=1 tools/vita_prepare_supervised_release.sh
```

The supervised script builds, deploys, verifies hashes, and leaves the app installed but stopped. The release gate checklist lives in `docs/vita-kart-64-release-gates.json`.

## Porting notes for other N64 decompilation projects

The Vita-specific work is intentionally separated into reusable pieces where practical:

- deterministic O2R storage conversion: `tools/vita_optimize_o2r.py`
- shader manifest promotion: `tools/vita_promote_runtime_cache.py`
- texture CI/TLUT warmup planning: `tools/vita_generate_texture_pairs.py`
- supervised hardware evidence and triage: `tools/vita_after_supervised_run.sh`
- Vita porting research/playbook: `docs/vita-n64-porting-playbook.md`

## Upstream credits

This project stands on n64decomp/mk64, HarbourMasters/SpaghettiKart, libultraship, Torch, VitaSDK, vitaGL, VitaShaRK, SDL2, and the broader Vita homebrew ecosystem. See `NOTICE.md` and bundled license files.
