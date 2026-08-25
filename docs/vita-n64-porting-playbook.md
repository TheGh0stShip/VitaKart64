# N64 decomp/static recomp to PS Vita porting playbook

## Goal

A Vita N64 port should not behave like a desktop renderer squeezed onto handheld hardware. It should front-load expensive work, use Vita-native formats where possible, and make every hardware test run produce reusable cache data.

This playbook is based on the Vita Kart 64 work and is intended to transfer to other N64 decompilation or static recompilation projects using libultraship-style resources, Fast3D display lists, VitaGL, or equivalent runtime asset archives.

## Product rules for Vita Kart 64

- Title: Vita Kart 64.
- Target hardware: real PS Vita, not PSTV as the primary tuning target.
- Performance policy: always max performance, no separate profiles.
- Expected clocks: ARM 500 MHz, GPU 222 MHz, XBAR 166 MHz.
- Target: locked 60 fps on hardware.
- Build/test policy while hardware tester is unavailable: no build, install, or launch.
- Deployment policy: install stopped; launch only when supervised.

## Porting architecture

### Engine-level reusable layer

Create a small Vita runtime-cache layer that every N64 Vita port can reuse.

Responsibilities:

- Force clocks and runtime policy once at boot.
- Present a real loading screen before VitaGL/default splash can leak through.
- Read archive/resource preload manifests.
- Pin resource objects so archive-backed pointers remain valid.
- Reserve texture IDs up front.
- Preload direct RGBA/I/IA textures.
- Preload CI4/CI8 textures with known TLUT resources.
- Precompile shader programs from packaged and runtime manifests.
- Warm audio banks/sequences/samples without output when backend support exists.
- Persist cache misses from supervised diagnostic builds.

Keep renderer-specific details here. Game code should not know about VitaGL texture IDs, GL formats, texture cache eviction, or TLUT staging.

### Game-specific layer

Each game should provide data, not custom renderer behavior.

Game responsibilities:

- Define resource groups that must be resident for gameplay.
- Generate or package warmup manifests.
- Provide naming heuristics only as a fallback.
- Feed runtime miss logs back into packaged seed manifests.
- Keep ROM-derived asset archives separate from generated cache metadata where possible.

## Startup pipeline

Recommended boot order:

1. Apply Vita clocks and disable adaptive performance behavior.
2. Initialize minimal display/loading screen.
3. Open archive and prefetch archive metadata.
4. Load packaged shader and texture-pair manifests.
5. Precompile shader programs.
6. Load and pin runtime resources.
7. Reserve texture slots.
8. Upload direct textures.
9. Upload manifest CI/TLUT texture pairs.
10. Warm audio banks and sequence metadata.
11. Invalidate transient renderer bindings.
12. Enter game loop.

The loading screen should show phase, current item counts, elapsed time, and whether cache manifests were found. A long loading phase is acceptable if it eliminates gameplay hitches; an opaque spinner is not acceptable.

## Texture strategy

### Direct textures

Preload textures that do not need runtime palette state:

- RGBA32.
- RGBA16.
- I4/I8.
- IA4/IA8/IA16.

On Vita, prefer native RGBA5551 upload for RGBA16 instead of expanding to RGBA8888.

### CI/TLUT textures

CI textures are the main first-use hitch risk.

Problems:

- CI4/CI8 GPU texture contents depend on the TLUT used at draw time.
- A CI image alone is not enough to build the final GL texture.
- Lazy first draw pays CPU expansion plus GPU upload on a render-critical frame.
- Address-based palette cache keys can prevent warmup hits if staging behavior differs.

Policy:

- Provide an engine API for `texture + palette + palette_index` warmup.
- Generate `texture-pairs.manifest` from archive naming rules, display-list scans, and supervised runtime miss logs.
- Use native RGBA5551 upload for expanded CI textures on Vita when supported.
- Support partial TLUT resources; many games do not store full 256-entry palettes for every CI8 texture.
- Keep a diagnostic logger disabled in release builds, because logging on misses creates artificial stutter.

## Shader strategy

Shader compile/link must be deterministic before gameplay.

Use three sources:

- Packaged seed manifest for known game coverage.
- Vita-local runtime manifest for observed misses.
- Synthetic preset warmup for broad common Fast3D combine modes.

Supervised test runs should harvest the Vita-local manifest and merge it into the packaged seed. Release builds should then warm those IDs at startup.

## Audio strategy

Audio should be warmed as deliberately as graphics.

Targets:

- Load banks and sequences during boot.
- Allocate voices/channels up front.
- Prime decode paths without audible output if backend supports it.
- Log first-use sample/bank misses in diagnostic builds.

Avoid changing audio scheduling blindly while tuning graphics. Audio regressions can look like performance issues because underruns add CPU spikes and user-visible instability.

## Archive strategy

Vita storage behavior is part of performance.

Rules:

- Store frequently-read runtime assets uncompressed.
- Keep startup-critical files early and contiguous.
- Group track, kart, HUD, item, and post-race assets by use phase.
- Avoid repushing large ROM-derived archives during code-only iterations.
- Put generated manifests in app/data files so they can change without rebuilding ROM-derived assets.

## Diagnostics workflow

Normal release iteration:

1. Build with diagnostics disabled.
2. Install stopped.
3. Launch only when hardware tester can observe hardware.
4. Record subjective stutter locations and visible artifacts.
5. Harvest runtime cache manifests.
6. Merge harvested data into packaged seeds.
7. Rebuild normal release.

Diagnostic iteration:

1. Build with `VITAKART_TEXTURE_MISS_LOG=1` only when supervised.
2. Reproduce hitches.
3. Pull `ux0:data/vitakart64/texture-misses.log`.
4. Merge it into `assets/vita/texture-pairs-extra.manifest`.
5. Rebuild without diagnostics.

Crash workflow:

1. Pull latest dump with `tools/vita_pull_latest_crash.py`.
2. Symbolicate against the exact installed `eboot.bin`.
3. Fix the crash once, then keep the latest-crash script in the loop.

## Common anti-patterns

- Tuning for Vita3K behavior instead of real Vita hardware.
- Adding per-frame logging to diagnose stutter.
- Increasing shader warmup endlessly when texture uploads are the real misses.
- Letting deploy scripts launch automatically after install.
- Rebuilding or repushing the large asset archive for code-only changes.
- Treating second-lap smoothness as success; cold first-use smoothness is the target.
- Adding visual quality features before fixing viewport artifacts and frame pacing.
- Using adaptive performance profiles when the product policy is always max performance.

## Reusable deliverables for future ports

Minimum reusable set:

- `VitaRuntimeCache` API for shaders, direct textures, CI/TLUT textures, audio warmup, and progress reporting.
- `texture-pairs.manifest` format.
- `shader-manifest.txt` merge tooling.
- Runtime miss logger gated by compile-time flag.
- Runtime cache harvest comparison tool.
- CI/TLUT coverage audit tool.
- Archive optimizer that stores selected files uncompressed and ordered by use phase.
- Install-stopped deploy helper.
- Supervised-run guard for build/install helpers.
- Latest-crash pull helper.

Nice-to-have reusable set:

- Offline display-list scanner for exact shader and texture/TLUT extraction.
- Cache versioning keyed by app version and asset archive hash.
- Startup loading screen with deterministic phase reporting.
- Perf HUD that can be compiled out of release builds.
- Audio warmup manifest generator.

## Vita Kart 64 next supervised acceptance checks

The next supervised build should answer these questions:

- Does startup complete with the new CI/TLUT preload volume?
- Does memory remain below a safe Vita threshold after preloading 9,310 texture pairs?
- Does race start stutter decrease or disappear?
- Do kart-heavy scenes avoid first-observed animation hitches?
- Is the post-race score screen materially smoother on first entry?
- Does audio still work?
- Are right/bottom border artifacts still absent?
- Does the app remain stable after closing and reopening?

If memory or startup time is too high, cap manifest warmup by phase instead of removing the CI/TLUT infrastructure. The infrastructure is correct; the policy may need per-phase budgeting.

## Warmup budgeting policy

Default release policy should be unlimited warmup when memory and startup time allow it. Add a compile-time or manifest-controlled budget as a fallback, not as a separate performance profile. If a full warmup is too expensive, split manifests by phase or priority so critical HUD/post-race/race-start assets still warm before gameplay.

## Manifest ordering contract

Generated texture-pair manifests should be ordered by gameplay value, not by raw archive order. Critical common/HUD/post-race UI pairs should appear before bulk animation data. For kart-style animation sets, order by animation frame first and character second so a capped warmup covers early frames for all racers instead of every frame for one racer. This keeps fallback caps useful without changing the default unlimited warmup policy.

## Texture manifest sizing

Use `tools/vita_texture_manifest_stats.py` before a supervised build to estimate native texture payload from a `texture-pairs.manifest`. This does not account for driver/object overhead, but it gives a fast lower bound for whether full CI/TLUT warmup is plausible on Vita hardware.

## Build flag dependency tracking

Compile-time tuning flags should be emitted into a generated header that object files depend on. Do not rely only on `-D` command-line changes; plain Make may otherwise reuse stale objects when switching between release, diagnostic, and capped warmup builds.

## Host-only preflight

Every N64-to-Vita port should have a host-only preflight that checks local SDK/tooling paths, required runtime assets, generated manifests, and estimated warmup memory. It should never build, deploy, or touch hardware; its job is to protect the supervised hardware window from obvious local setup mistakes.

## Manifest shaping tools

Keep the generated full warmup manifest as the source of truth. If a handheld target cannot afford full startup warmup, use a deterministic filter tool to create a smaller critical or capped manifest. This is better than ad hoc edits because it preserves repeatability and lets future ports define their own critical resource directories.

Phase planning is the safer fallback before removing coverage. A tool such as `tools/vita_plan_cache_phases.py` should split full texture-pair coverage into startup, menu, race-common, post-race, kart, course, and other groups so a port can move work to scene-loading boundaries without inventing separate performance profiles.

## Persistent hardware-discovery overlays

Do not merge supervised runtime discoveries directly into a generated manifest. Keep an overlay such as `assets/vita/texture-pairs-extra.manifest` and let the build regenerate the packaged manifest from deterministic archive scanning plus that overlay. This preserves hardware findings across generator updates and keeps generated data separate from observed data.

## Build script preflight integration

The normal build/install helper should call the host-only preflight before compilation and deployment. Provide an explicit skip flag for expert use, but make the safe path the default. This prevents wasting hardware test windows on local setup drift.

## TLUT resources are not display textures

When preloading archive textures, do not upload TLUT palette resources as standalone GPU textures. They should be loaded and pinned as resources, then consumed by CI/TLUT pair warmup. Uploading every TLUT as a direct RGBA16 texture wastes startup time, texture IDs, driver objects, and GPU memory without reducing gameplay stutter.

## CI/TLUT manifest validation

Manifest tooling should verify more than file existence. It should inspect CI texel indices and paired TLUT payload sizes so partial palettes are accepted only when every referenced index is present. This is especially important for animation-heavy games that store thousands of small partial TLUT resources.

## Deployment verification

Install-stopped deploy helpers should verify every pushed app/runtime artifact by hash unless explicitly disabled. A fast but unverified push can waste far more time if the next hardware run is testing stale or partially transferred content.

## Build interpreter preflight

If a port's Makefile uses a project-local Python interpreter for generated assets, the host-only preflight should check that exact interpreter or the `PYTHON` override before compilation begins. This catches missing virtual environments and dependency drift before a supervised hardware window.

## Release evidence manifests

Every supervised hardware iteration should produce a local evidence JSON with artifact hashes, build flags, cache-manifest statistics, and title ID. This prevents confusing hardware observations across similar builds and gives crash symbolication an exact installed executable hash.

## Hardware report scoring

Use a host-only scorer after a supervised run report is filled. The scorer should convert startup, audio, stutter, artifact, persistence, crash, and cache-growth fields into pass/warn/fail plus a next-action list. This keeps future N64 Vita ports from relying on memory or vague impressions after a hardware session.

## Install-stopped verification

A no-launch deploy should verify stopped state through the device app-status API, not only issue a best-effort kill. Keep an explicit bypass for bridge failures, but make checked stopped-state the default so unattended or deferred hardware runs do not accidentally leave the title running.

## Two-stage generated-asset preflight

When generated assets depend on the same interpreter/toolchain being checked, use two-stage preflight. Stage one checks setup and source inputs. The build script then generates lightweight derived assets. Stage two validates generated manifests before expensive compilation or hardware deployment.

## Build flag validation

Generated build-config headers should be fed only validated values. Preflight should reject non-boolean diagnostic flags and nonnumeric warmup limits before compilation, because invalid generated defines waste supervised build time and can leave confusing partial outputs.

## Hardware observation reports

Generate a timestamped hardware-run report for every installed build. The report should reference exact release evidence and force observations into categories that map directly to future fixes: startup, audio, first-use stutter, post-race, visual artifacts, persistence, crash data, and next decision.

## Resource warmup planning

Resource warmup should get the same treatment as texture-pair warmup. A host-side planner such as `tools/vita_plan_resource_warmup.py` can classify textures, models, audio, courses, and misc data by rough scene phase so remaining stutter can be traced to audio/archive/scene work instead of assuming every hitch is a shader or texture miss.

## Cross-applicable porting checklist - 2026-08-25

Use this order for another N64 decomp port targeting Vita:

1. Establish a no-launch supervised deploy path before performance work begins.
2. Disable middleware splash screens and own the loading screen from the app.
3. Lock max clocks and rendering policy before resource loading starts.
4. Generate a complete archive/resource census from the packaged O2R.
5. Split resources into texture, model, audio, and other preload groups.
6. Generate CI texture/TLUT pairs offline, then keep a persistent overlay for supervised hardware-discovered misses.
7. Reserve backend texture IDs and texture-cache map capacity before uploading prewarmed resources.
8. Prefer Vita-native RGBA5551 upload paths for RGBA16 and CI+TLUT output.
9. Cache GL sampler/filter/binding state and avoid global invalidation unless policy changes.
10. Seed shaders with known combiner presets, then merge only supervised runtime-harvested shader variants.
11. Clamp presentation rectangles to exact 960x544 when they are intended to cover the full Vita screen.
12. Collect frame hitches, preload summaries, texture misses, and crash dumps with scripts; never rely on manual filename transcription.
13. Keep diagnostic logs compile-time gated and disabled in release builds.
14. Treat post-race/scoreboard/menu scenes as mandatory performance gates, not secondary screens.
15. Record every supervised run in a hardware-run report with artifact hashes and build flags.
