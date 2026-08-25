# Vita N64 decomp/static recomp porting research

## Current Vita Kart 64 performance thesis

The remaining hitches are most consistent with first-use runtime work, not steady-state throughput. Race laps become smoother after content has appeared once, and the post-race score screen improves after it runs briefly. That points at lazy GPU texture creation/upload, CI/TLUT expansion, shader program compilation, audio voice/bank initialization, or archive reads happening on render/audio-critical frames.

The existing Vita Kart 64 work already handles the broad cases:

- Vita clocks are forced high instead of using selectable profiles.
- The asset archive is stored rather than deflated for deterministic reads.
- Runtime resources are loaded and kept resident.
- Non-paletted textures are preloaded into the GL texture cache.
- Shader IDs are warmed from a packaged seed manifest plus a persistent runtime manifest.
- VitaGL texture capacity was raised and texture IDs are reserved up front.

The main uncovered class is paletted CI4/CI8 textures. These cannot be fully preloaded from only the image resource because the final GPU texture depends on the TLUT used with it. First observing a CI texture plus palette pair can still force CPU expansion and GPU upload during gameplay.

## High-leverage reusable infrastructure

### 1. Vita runtime cache builder

Create a reusable engine layer, not an MK64-only hack, that can warm all high-cost runtime objects before gameplay.

Responsibilities:

- Load and pin selected archive resources.
- Reserve GPU texture IDs.
- Upload direct RGBA/I/IA textures.
- Upload CI/TLUT-expanded textures when a texture and palette pair is known.
- Compile/link shader programs from a seed and persistent manifest.
- Optionally initialize audio banks, sequences, and voice pools.
- Report progress to a frontend loading screen.

The engine layer should expose APIs like:

```cpp
bool PreloadTextureResource(const std::shared_ptr<Fast::Texture>& texture);
bool PreloadTextureResourceWithPalette(const std::shared_ptr<Fast::Texture>& texture,
                                       const std::shared_ptr<Fast::Texture>& palette,
                                       uint8_t paletteIndex);
void PrewarmShaderPrograms(const ShaderManifest& manifest);
void PrewarmAudioBanks(const AudioWarmupManifest& manifest);
```

Game-specific code should only provide manifests or hints. VitaGL details, texture cache keys, and TLUT staging stay inside the engine.

### 2. Offline display-list warmup scanner

The final robust solution is an offline tool that opens the O2R/OTR archive, loads display-list resources, walks render commands, and records exact runtime combinations.

Outputs:

- `shader-manifest.txt`: observed or statically derived shader IDs.
- `texture-pairs.manifest`: CI texture path, TLUT path, palette index, size, format.
- `resource-preload.manifest`: archive paths needed before gameplay.
- `audio-preload.manifest`: banks/sequences/samples that should be resident.

Benefits:

- No dependence on players manually discovering shaders/textures through gameplay.
- Persistent across builds because manifests can be generated and packaged.
- Reusable for other N64 decomp/static recomp projects using the same archive/resource system.

Risk:

- The scanner needs enough RDP/F3DEX interpretation to model `SetTextureImage`, `SetTile`, `LoadTlut`, `LoadBlock`, and nested `G_DL` calls. It should start as a conservative extractor, not a complete renderer.

### 3. Runtime observation manifest

Keep recording misses at runtime, but make them structured and portable.

Record:

- Shader program ID misses.
- Texture cache misses with resource path, format, size, palette path if known, palette index, and screen/game phase.
- Audio bank/sample first-use misses.
- Archive load timing spikes.

Persist under `ux0:data/<title>/runtime-cache/`. A desktop or build-time tool can merge these into packaged seed manifests. This turns hardware test runs into durable optimization data.

### 4. Asset packaging for Vita memory behavior

For Vita, archive layout matters because slow or fragmented reads show up as hitches.

Rules:

- Store high-frequency runtime entries uncompressed.
- Put startup-critical files early in archive order.
- Group racing HUD, karts, track models/textures, and post-race UI contiguously.
- Keep generated manifests outside the ROM-derived asset archive when possible so rebuilds are fast and legally cleaner.

### 5. Audio warmup

Audio hitches and no-sound regressions should be handled as a first-class cache target.

Warmup candidates:

- Open and decode all banks/sequences during loading.
- Allocate voice/channel structures up front.
- Prime ADPCM/sample conversion paths with a muted non-output warmup if the backend supports it.
- Log first-use sample misses in the runtime observation manifest.

### 6. VitaGL/runtime-specific policies

Runtime policies should be fixed for this product:

- Always max clocks: CPU 500 MHz, GPU 222 MHz, XBAR 166 MHz.
- No separate performance profiles.
- Avoid lazy allocation on render-critical frames.
- Avoid per-frame logging or tracing unless explicitly compiled in.
- Avoid framebuffer clears/copies larger than the game viewport unless needed.
- Prefer stable native resolution and shader/texture determinism over adaptive behavior.

## Vita Kart 64 immediate priorities

### Done or source-prepped

- Direct texture preload.
- Shader warmup from seed plus persistent manifest.
- Stored O2R archive.
- Higher VitaGL texture capacity.
- Custom loading screen path.
- CI/TLUT preload API and MK64 naming-heuristic pairing source prep.

### Next hardware-observed build target

- Build and install only when hardware tester can observe the Vita.
- Do not launch unattended.
- Test start-of-race, first item effects, lap transitions, and post-race score screen.
- Check whether the CI/TLUT source prep reduces rank/font/item/portrait/post-race first-use hitches.

### Next source targets if stutter remains

1. Add structured runtime miss logging for texture cache misses with resource and palette paths.
2. Generate `texture-pairs.manifest` from the logged misses and package it with the app.
3. Extend preload to consume explicit pair manifests instead of only naming heuristics.
4. Add audio bank/sample first-use logging and warmup.
5. Build the offline display-list scanner once runtime logs prove which command patterns matter.

## Product polish ideas that should not risk 60 fps

- Title: Vita Kart 64.
- Loading screen: N64-inspired full-screen screen with phase, current item, elapsed time, and progress counts.
- Startup cache status: show whether packaged manifests and runtime manifests were found.
- Optional cache rebuild notice if manifests are stale.
- Cleaner text/UI scaling only if it does not add GPU cost during gameplay.
- Avoid expensive antialiasing. Prefer correct viewport, texture filtering policy, and framebuffer artifact fixes first.

## Success criteria

- Cold launch reaches menu without visible VitaGL/default splash leakage.
- First race start does not hitch noticeably.
- New item effects, karts, lap banners, and post-race score screens do not cause frame spikes.
- Audio starts reliably and remains synchronized.
- Races hold 60 fps under max clocks on real PS Vita hardware.
- Runtime manifests stop growing during normal playthrough coverage, proving warmup coverage is complete.

## Diagnostic build switches

`VITAKART_TEXTURE_MISS_LOG` enables texture-cache miss logging to `ux0:data/vitakart64/texture-misses.log`. It is intentionally compile-time disabled for performance builds because file I/O on a first-use miss would make the hitch being measured worse. Use it only for supervised diagnostic builds, then fold the resulting misses into a packaged warmup manifest.

## Manifest-based CI/TLUT warmup

`tools/vita_generate_texture_pairs.py` generates `assets/vita/texture-pairs.manifest` from archive path names. The runtime preload path now reads `app0:/texture-pairs.manifest` and `ux0:data/vitakart64/texture-pairs.manifest` before falling back to name heuristics. This creates a clean route for future ports: improve or replace the generator without changing VitaGL or renderer code.

Deployment policy was also tightened: `tools/vita_deploy_release.sh` no longer launches by default. Set `VITAKART_LAUNCH_AFTER_DEPLOY=1` only when a supervised launch is desired.

## Supervised diagnostic-to-seed workflow

For a normal performance build, leave `VITAKART_TEXTURE_MISS_LOG` undefined. The packaged `assets/vita/texture-pairs.manifest` is regenerated from `mk64-vita.o2r` by `Makefile.vita` through `tools/vita_generate_texture_pairs.py`, then merged with the persistent hardware-discovery overlay at `assets/vita/texture-pairs-extra.manifest`.

For a supervised diagnostic build only:

1. Compile with `VITAKART_TEXTURE_MISS_LOG` defined.
2. Run through the scenes that still hitch: race start, first item effects, lap transitions, and post-race score screen.
3. Copy `ux0:data/vitakart64/texture-misses.log` back to the project.
4. Run `tools/vita_merge_texture_misses.py <copied-log> assets/vita/texture-pairs-extra.manifest`.
5. Rebuild without `VITAKART_TEXTURE_MISS_LOG` so the generated archive seed plus hardware-discovery overlay are packaged without runtime file-I/O overhead.

This same flow should apply to future N64 Vita ports: the renderer logs exact resource/palette misses, a project tool merges them into a seed manifest, and the release build consumes the manifest during startup warmup.

## Supervised build/install workflow

Use `tools/vita_build_install_stopped.sh` for the normal supervised hardware iteration. It builds `vita-kart-64.vpk`, deploys changed runtime files through VitaDevBridge, and leaves `VITAKRT64` stopped. It does not launch unless the deploy script is explicitly run with `VITAKART_LAUNCH_AFTER_DEPLOY=1`.

By default, `tools/vita_deploy_release.sh` does not repush `mk64-vita.o2r`, because the optimized archive is large and does not change during code-only tuning. Set `VITAKART_PUSH_ARCHIVE=1` when the archive has changed or a clean Vita install needs the asset archive.

## Crash dump retrieval

Use `tools/vita_pull_latest_crash.py` after a supervised crash. It scans common Vita dump locations through VitaDevBridge, picks the newest `*-eboot.bin.psp2dmp`, and pulls it into `crashes/`. This removes the manual filename-copy step that slowed earlier debugging loops.

## Runtime cache harvest helper

After a supervised hardware run, use `tools/vita_collect_runtime_cache.py` to pull runtime cache evidence from the Vita into `runtime-cache/<utc-stamp>/`. It attempts to collect `shader-manifest.txt`, `texture-misses.log`, and `texture-pairs.manifest` from `ux0:data/vitakart64/`.

Unless `--no-merge` is passed, it merges observed shaders into `assets/vita/shader-manifest.txt` and texture misses into `assets/vita/texture-pairs-extra.manifest`. The intended loop is supervised run, harvest, rebuild release without diagnostic logging, install stopped, then supervised run again.

## Diagnostic build helper

Use `tools/vita_build_install_diagnostic_stopped.sh` only when hardware tester can immediately run a supervised hardware session. It forces a rebuild with `VITAKART_TEXTURE_MISS_LOG=1`, installs the diagnostic build, and leaves the app stopped. After harvesting `texture-misses.log`, rebuild normally with `tools/vita_build_install_stopped.sh` so release testing is not polluted by miss-log file I/O.

## Current next-build optimization hypothesis

The generated CI/TLUT manifest now includes kart wheel animation pairs using the `*_frame000_wheel0` to `*_000_tlut_wheel_0` naming convention. This expands coverage from the obvious HUD/post-race pairs to the high-volume kart animation set.

To keep this viable on Vita, CI and RGBA16 uploads now use native RGBA5551 upload paths when VitaGL supports them. For CI textures this preserves the original N64 palette precision while reducing upload bandwidth and GPU texture storage versus RGBA8888 expansion. Partial CI8 palettes are also supported, which matters for kart TLUT resources that contain only the used low palette range.

## Portable Vita/N64 decomp optimization layer - 2026-08-25

The reusable path for future N64 decomp ports on Vita is not a game-specific pile of fixes. It should be a thin platform layer with explicit responsibilities:

1. Boot policy: force max clocks once at process start and reassert performance-critical CVars after config loads. Avoid user-facing performance profiles; the Vita target should always choose the known-good locked-60 configuration.
2. Resource residency: enumerate O2R/archive resources up front, keep render-critical textures/models/audio resident, and avoid lazy decode on the first visible frame.
3. Paletted texture prewarm: pair CI4/CI8 textures with TLUTs offline, package a generated manifest, support a persistent extra overlay for hardware-discovered misses, and upload native RGBA5551 on Vita to avoid per-frame conversion churn.
4. Shader coverage: seed the packaged shader manifest with both generic combiner presets and runtime-harvested variants. Persist harvested variants as source-controlled seed data only after a supervised hardware run proves them useful.
5. GL state reduction: cache sampler/filter/bind state in the backend, reserve texture IDs before prewarm, and invalidate backend caches only when policy actually changes.
6. Presentation correctness: clamp near-fullscreen viewports/scissors to exact 960x544 and treat right/bottom border artifacts as presentation-rect bugs first, not game-logic bugs.
7. Evidence-first diagnostics: diagnostics must be compile-time gated and off in release builds. Texture misses, frame hitches, preload counters, and crash dumps should be collected by scripts after a supervised run, not typed manually.
8. Loading UX: replace middleware splash screens with a full-screen project loading screen that exposes elapsed time, estimated remaining time, preload phase, resource counts, and cache status.

For other decomp ports, the first reusable artifact should be a `vita_port` support package containing: max-clock boot setup, O2R resource census, texture/TLUT manifest generation, shader-manifest merge, preload summary writing, frame-hitch summary, deploy-stopped guard, and a standardized hardware-run report template.

## Primary-source notes checked 2026-08-25

Sources checked during unattended local-only work:

- vitaGL upstream documents performance and compatibility flags including `NO_DEBUG=1`, `SAMPLERS_SPEEDHACK=1`, `USE_SCRATCH_MEMORY=1`, `HAVE_SHADER_CACHE=1`, and `NO_SPLASHSCREEN=1`: https://github.com/rinnegatamante/vitagl
- SpaghettiKart upstream documents the supported US ROM/O2R flow and confirms the asset archive model this Vita port is packaging around: https://github.com/HarbourMasters/SpaghettiKart
- DaedalusX64-vitaGL release notes show relevant N64-on-Vita patterns: shader cache use, reducing unnecessary cache invalidation, pre-reserving fragment cache vectors, NEON RDRAM hashing, removing unnecessary `glFinish`, and respecting viewport/scissor behavior: https://github.com/Rinnegatamante/DaedalusX64-vitaGL/releases
- VitaSDK samples include power/callback examples under `<psp2/power.h>` and are the primary public sample source for Vita-side system integration patterns: https://github.com/vitasdk/samples/blob/master/power/src/main.c

Implications for Vita Kart 64:

1. Keep the current vitaGL vendor policy strict: shader cache, scratch memory, sampler speedhack, no debug, and no middleware splash.
2. Do not add risky vitaGL flags just because they sound faster. Upstream marks several speedhacks as potentially crashy or glitch-prone; this port already has a history of presentation artifacts and should avoid new renderer risk until the current supervised build is measured.
3. The DaedalusX64-vitaGL pattern supports the current direction: fewer broad invalidations, pre-reserved caches, shader cache persistence, and presentation-rect correctness are more defensible than random draw-speed hacks.
4. O2R/archive-first prewarm is the right abstraction for this project and for future HarbourMasters/N64 decomp Vita ports because it operates on packaged resource names rather than scene-specific source code guesses.

## 2026-08-25 cache harvest safety update

`tools/vita_collect_runtime_cache.py` now defaults to harvest-only behavior. Use `tools/vita_promote_runtime_cache.py --dry-run` to review promotable shader and texture-pair seeds, then promote explicitly. Passing `--merge` to the collector is supported for intentional legacy-style source updates, but it is not the preferred release flow.
