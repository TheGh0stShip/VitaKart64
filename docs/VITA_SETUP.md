# Vita Kart 64 setup and build guide

This guide builds the source/tooling release into a local VPK. The repo does not provide ROMs, generated game archives, or public binary packages.

## 1. Host prerequisites

Recommended host: Linux or WSL2 with a case-sensitive checkout.

Debian/Ubuntu host packages:

```sh
sudo apt update
sudo apt install -y build-essential git make cmake ninja-build pkg-config \
  python3 python3-venv python3-pip ccache rsync zip unzip curl ca-certificates \
  libpng-dev libzip-dev libsdl2-dev libsdl2-net-dev libtinyxml2-dev \
  libogg-dev libvorbis-dev libssl-dev zlib1g-dev libzstd-dev libbz2-dev \
  liblzma-dev
```

Python packages:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

`Pillow` is included for image tooling compatibility.

## 2. VitaSDK

Install VitaSDK using the upstream VitaSDK/vdpm flow, then export:

```sh
export VITASDK=/usr/local/vitasdk
export PATH="$VITASDK/bin:$PATH"
```

The VitaSDK site documents the SDK and porting package flow, and vdpm is the SDK package manager used below.

Suggested Vita packages for this project:

```sh
vdpm install zlib bzip2 zstd xz openssl libpng libzip tinyxml2 sdl2 \
  libogg libvorbis yaml-cpp vitashark taihen mathneon
```

If a package name differs on your SDK snapshot, use `vdpm search <name>` and install the matching Vita package.

## 3. Build local vitaGL

The Vita release uses a locally built vitaGL archive with this policy:

```text
HAVE_SHADER_CACHE=1 NO_DEBUG=1 USE_SCRATCH_MEMORY=1 SAMPLERS_SPEEDHACK=1 NO_SPLASHSCREEN=1
```

Build it with:

```sh
tools/vita_build_vitagl_vendor.sh
```

That script clones vitaGL into `build/vitagl-src`, checks out the pinned commit, applies the Vita Kart compatibility patch if needed, builds `vendor/vitagl/libvitagl.a`, and writes `vendor/vitagl/BUILD.txt`.

## 4. Provide your ROM and generate local archives

Only the US ROM is supported. Verify your dumped ROM SHA-1:

```text
579C48E211AE952530FFC8738709F078D5DD215E
```

Generate `mk64.o2r` using the upstream Spaghetti Kart extraction flow, then place it in the repo root:

```sh
cp /path/to/mk64.o2r ./mk64.o2r
```

Convert the archive to deterministic stored entries for Vita startup and preload behavior:

```sh
tools/vita_optimize_o2r.py mk64.o2r mk64-vita.o2r
```

Generate `spaghetti.o2r` from this checkout:

```sh
cmake -S . -B build-cmake -GNinja -DCMAKE_BUILD_TYPE=Release
cmake --build build-cmake --target GenerateO2R
cp build-cmake/spaghetti.o2r ./spaghetti.o2r
```

If your CMake build writes `spaghetti.o2r` somewhere else, copy that file to the repo root before the Vita make step.

## 5. Build the VPK

```sh
make -f Makefile.vita -j"$(nproc)" vita-kart-64.vpk
```

The Makefile generates Vita loading/LiveArea art, shader/resource manifests, `eboot.bin`, `param.sfo`, and `vita-kart-64.vpk`.

## 6. Install on hardware

Manual path:

```sh
# Copy vita-kart-64.vpk to the Vita and install with VitaShell.
# Place mk64.o2r on the Vita as ux0:data/vitakart64/mk64.o2r.
```

Automated path with VitaDevBridge/VitaCompanion:

```sh
export VDB_ROOT="$HOME/projects/VitaDevBridge"
export VDB_CONFIG="$VDB_ROOT/.vitadevbridge/your-paired-vita.toml"
VITAKART_SUPERVISED_HARDWARE_RUN=1 tools/vita_prepare_supervised_release.sh
```

The automated path deploys files and leaves the app installed but stopped. Launch manually on the Vita for release gate observation.

## 7. Post-run evidence

After a supervised hardware run:

```sh
VITAKART_SUPERVISED_HARDWARE_RUN=1 tools/vita_after_supervised_run.sh
```

To promote runtime-discovered shader/texture cache entries after reviewing the preview:

```sh
VITAKART_SUPERVISED_HARDWARE_RUN=1 VITAKART_PROMOTE_RUNTIME_CACHE=1 tools/vita_after_supervised_run.sh
```
