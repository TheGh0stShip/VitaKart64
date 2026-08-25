# Vita/N64 support package architecture

This document defines the reusable layer that should be extracted from Vita Kart 64 after the next supervised hardware pass. The point is to stop solving the same Vita problems one port at a time.

## Scope

The support package should serve HarbourMasters-style and N64 decomp-derived ports that use packaged resource archives, a Fast3D/OpenGL-style renderer path, and Vita homebrew deployment.

It should not own game logic, copyrighted data, ROM extraction, or game-specific UI behavior.

## Package boundaries

### `vita_boot`

Responsibilities:

1. Apply max clocks at process start.
2. Reapply performance-critical rendering CVars after config load.
3. Disable user-facing performance profiles for Vita release builds.
4. Reset stale runtime evidence at app start so each run is diagnosable.
5. Register power/suspend callbacks only if the target port needs suspend diagnostics.

Default policy:

```text
ARM 500 MHz
BUS 222 MHz
GPU 222 MHz
XBAR 166 MHz
Target FPS 60
VSync on
Adaptive resolution off
MSAA minimal/off unless hardware proves it is free
Alternate assets off by default
```

### `vita_archive_census`

Responsibilities:

1. Enumerate packaged O2R/ZIP resources.
2. Classify resources into texture, palette, model, audio, scene, shader, and other groups.
3. Emit deterministic manifests for preload and evidence reports.
4. Estimate GPU upload payloads before a build is attempted.
5. Fail supervised release builds when required resource classes are incomplete.

The key design rule is archive-first behavior. Do not guess at coverage from source filenames or scene code when the packaged archive can be enumerated directly.

### `vita_texture_warmup`

Responsibilities:

1. Generate CI4/CI8 texture-to-TLUT pairs offline.
2. Preserve a persistent overlay for supervised hardware-discovered misses.
3. Preload/pin render-critical texture resources.
4. Upload Vita-native `RGBA5551` when source data maps cleanly to N64 `RGBA16`.
5. Reserve renderer texture IDs before bulk upload.
6. Grow texture-cache capacity to hold the warmup set without eviction churn.

Release invariant:

```text
texture_pair_limit = 0
full_ci_tlut_coverage = true
texture_miss_log = false
```

Diagnostic invariant:

```text
texture_miss_log may be enabled only for one supervised diagnostic run
diagnostic discoveries must be merged into the overlay deliberately
release builds must return to texture_miss_log = false
```

### `vita_shader_warmup`

Responsibilities:

1. Seed known Fast3D/N64 combiner presets.
2. Merge supervised runtime-harvested shader variants into a packaged seed.
3. Keep middleware shader-cache support enabled.
4. Avoid runtime compilation during first visible presentation where possible.

Release invariant:

```text
packaged shader seed exists
middleware shader cache enabled
runtime cache harvesting disabled
```

### `vita_renderer_policy`

Responsibilities:

1. Cache texture bind state.
2. Cache sampler/filter/wrap state per texture.
3. Avoid broad GL cache invalidation when requested policy is already active.
4. Clamp intended-fullscreen viewport/scissor rectangles to exact Vita framebuffer dimensions.
5. Keep risky renderer speedhacks behind explicit supervised policy switches.

Presentation invariant:

```text
fullscreen width = 960
fullscreen height = 544
no right-edge retained frame strip
no bottom-edge reflected strip
no grey seam at presentation boundary
```

### `vita_loading_ux`

Responsibilities:

1. Own the user-visible loading screen.
2. Suppress middleware splash screens in release builds.
3. Report current phase, elapsed time, estimated remaining time, resource counts, GPU texture warmup count, and cache status.
4. Degrade gracefully when custom artwork is missing.

### `vita_audio_warmup`

Responsibilities:

1. Classify audio resources during archive census.
2. Preload/pin resources needed by menu, race start, lap events, item events, and post-race scoreboard.
3. Avoid expensive first-use decode or stream setup during race start and results transitions.
4. Record audio resource counts in preload evidence.

This layer should be conservative. Audio correctness is a release gate, so avoid speculative async behavior unless hardware evidence proves it helps.

### `vita_evidence`

Responsibilities:

1. Generate release evidence with artifact hashes and build flags.
2. Generate supervised hardware-run reports.
3. Generate human-fillable release-gate checklists.
4. Score filled checklists after hardware observation.
5. Bundle evidence after a supervised run.
6. Pull crash dumps automatically when requested awake; never require manual dump filename typing.

Release invariant:

```text
no claim of release-candidate status without PS Vita hardware evidence
no release-candidate status from Vita3K alone
no unattended hardware/build/run actions while hardware tester is asleep
```

## Extraction plan after Vita Kart 64 stabilizes

1. Keep Vita Kart 64 as the reference implementation until it passes the release gates.
2. Move generic scripts into a `vita-n64-support` directory.
3. Replace project-specific names with parameters: title, title ID, archive path, data directory, resource namespace, build command, deploy command.
4. Keep game-specific overlays in the game repo, not in the support package.
5. Document required integration points for a new port: boot hook, renderer API hooks, archive path, texture metadata parser, loading-screen callbacks, and evidence paths.
6. Use Vita Kart 64 run evidence as the baseline proof that the package works on real hardware.

## Anti-patterns to avoid

1. Shipping a faster-looking build with diagnostic logging accidentally enabled.
2. Treating Vita3K behavior as proof of hardware behavior.
3. Adding risky vitaGL speedhacks before isolating whether hitches are resource, shader, audio, or presentation related.
4. Debugging by manual crash filename transcription.
5. Rebuilding vendor libraries ad hoc without recording build flags.
6. Letting the middleware splash screen hide a long or stuck preload phase.
7. Calling a build final when post-race screens have not been tested.
8. Solving first-lap hitching with scene-specific hacks before archive coverage and shader coverage are proven complete.


## Release-gate data contract

The reusable support package should treat `docs/vita-release-gate-schema.md` as the local schema for release-gate manifests. Vita Kart 64 uses `docs/vita-kart-64-release-gates.json` as the current concrete instance.

Future ports should keep the same structure so checklist generation, filled-checklist scoring, run triage, and evidence bundling can be reused with minimal project-specific glue.

## Extraction map

`docs/vita-n64-support-extraction-map.md` maps the current Vita Kart 64 files into reusable package candidates, project-specific parameters, runtime-code candidates, and extraction order. Use it after Vita Kart 64 passes hardware release gates to avoid extracting unstable assumptions too early.
