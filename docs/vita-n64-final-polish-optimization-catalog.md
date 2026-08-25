# Vita N64 final-polish optimization catalog

Scope: Vita Kart 64 first, then reusable PS Vita support for other N64 decompilation ports.

This file is intentionally offline-only. It records candidate optimizations and release-quality checks that can be implemented without depending on Vita3K behavior. Hardware validation still waits for a supervised PS Vita run.

## Release target

- Platform: PS Vita hardware, not PSTV and not emulator-fit behavior.
- Clocks: ARM 500 MHz, GPU 222 MHz, XBAR 166 MHz, BUS 222 MHz.
- Performance target: locked 60 fps in race, race start, item/effect first-use, multi-kart scenes, post-race scoreboard, and ceremony.
- Presentation target: no right/bottom stale-frame artifacts, no gray seam, no middleware splash, Vita Kart 64 identity from launch through loading.
- Warmup target: no first-observation hitches after a clean app start, and explicit evidence when startup preloading completed.

## Highest-yield Vita Kart 64 optimizations

- `Full resource residency`: keep all runtime groups loaded once startup reaches the custom loading screen, because repeated archive/resource load during gameplay shows up exactly as first-observation stutter.
- `Native texture upload`: prefer RGBA5551/Vita-native texture paths where available, avoiding repeat conversion and avoiding generic fallback upload paths during race/post-race.
- `CI/TLUT pair coverage`: use the generated manifest first and heuristic pairing second; manifest coverage should trend toward complete so heuristic fallback becomes evidence of missing tooling coverage, not a normal runtime dependency.
- `Texture slot reservation`: reserve the target texture object capacity before warmup so startup pays allocation cost deterministically and gameplay does not grow the backend cache.
- `Shader seed packaging`: package a generated shader manifest from supervised hardware discoveries; do not rely on runtime discovery being repeated after close/reopen.
- `Phase-first preload order`: load common/menu, audio, ceremony/post-race, common model/other, karts, tracks, and long-tail resources in deterministic order to make startup progress understandable and ensure post-race assets are not last-minute work.
- `Presentation clamp`: clamp near-fullscreen viewport/scissor to 960x544 and invalidate bindings after bulk preload; border artifacts should be treated as a presentation policy bug, not hidden by overscan.
- `Audio first-class preload`: keep audio banks/sequences/samples in the same release warmup path so "60 fps but no sound" cannot pass release evidence.

## Cross-port reusable support package

- `vita_runtime_preload`: generic resource-group indexing, stable sort, residency vector, phase timing, and ready-marker emission.
- `vita_texture_manifest`: host generator for CI/TLUT texture-pair manifests, with bounds checks and estimated native upload size.
- `vita_shader_manifest`: runtime miss capture plus host merge/de-dupe tooling for packaged shader seeds.
- `vita_release_gates`: JSON manifest, checklist generator, checklist scorer, and evidence bundler.
- `vita_branding`: stdlib-only loading/icon/startup asset generation, plus freshness checks to avoid stale LiveArea packaging.
- `vita_supervised_deploy`: build/install-stopped wrapper, diagnostic-stopped wrapper, and explicit supervised-run guard.
- `vita_runtime_cache_harvest`: pull-only-after-supervision cache collector that mirrors latest runtime evidence without manual filename typing.

## Porting rules that should carry to other N64 decomps

- Do not optimize against Vita3K if hardware behavior conflicts; emulator is useful for packaging/smoke checks only.
- Do not ship separate performance profiles; release defaults should always be max-performance Vita clocks and diagnostics disabled.
- Do not let middleware default splash screens leak into the product; own the loading UX and show phase/progress/elapsed/remaining information.
- Do not trust "second lap is smoother" as success; first clean launch must be smooth after packaged warmup.
- Do not accept raw runtime misses as normal release behavior; every miss should either become a packaged seed or expose a deterministic generator gap.
- Do not let build tooling silently skip generated metadata; stale brand, shader, texture, or gate metadata should stop release packaging.

## Next supervised hardware evidence to collect

- Confirm custom loading screen replaces VitaGL/libultraship splash.
- Confirm preload summary and preload-ready marker exist after first launch.
- Confirm preload-ready marker existed before run on close/reopen.
- Confirm manifest CI/TLUT warmed count is high and heuristic warmed count is low or explainable.
- Confirm texture miss log is empty in release mode, or absent because logging is disabled.
- Confirm frame hitch log is absent in release mode, then use diagnostic-only stopped build if subjective stutter remains.
- Confirm post-race score screen does not hitch after a clean app start.
- Confirm no right/bottom presentation artifact across menu, race, transition, and post-race.

## Fast future wins

- Promote recurring runtime-discovered shader misses into the packaged shader manifest and texture misses into the durable texture-pair overlay immediately after supervised evidence collection.
- Add per-phase frame timing markers only in diagnostic builds, so first-start and post-race hitches can be mapped without leaving logging in release.
- Keep release artifacts tied to source-input hashes, gate manifest hash, texture manifest stats, and brand manifest hash.
- Extract Vita preload/render/cache helpers into a small support layer once Vita Kart 64 stabilizes, instead of copying project-specific scripts into the next decomp port.

## Persistent warmup promotion policy

- Runtime discovery is diagnostic evidence, not a release feature.
- A release candidate should package the shader and CI/TLUT seeds discovered on supervised hardware before it is judged for first-launch smoothness.
- `tools/vita_triage_supervised_run.py` should report promotable seed counts after cache harvest.
- `tools/vita_promote_runtime_cache.py` should be used to merge shader seeds into `assets/vita/shader-manifest.txt` and hardware-discovered texture pairs into `assets/vita/texture-pairs-extra.manifest` before the next supervised build.
- If promotable counts stay nonzero across builds, the generator or cache-harvest path is incomplete and should be fixed before more renderer changes are attempted.

## Shader cache correctness and full clamp-slot warmup

- Store shader program cache keys at full `(shader_id0, shader_id1)` width; truncating `shader_id1` loses shader-stack/high-option bits and can corrupt shader reuse.
- Build shader option bits with explicit 64-bit shifts.
- Warm all 16 runtime clamp-mode slots, because gameplay indexes `ColorCombiner::prg[tm]` with `tm` bits for texel0 S/T and texel1 S/T.
- Prewarm should populate both backend shader programs and interpreter combiner cache slots; backend-only warmup still leaves first-use combiner map insertion and program-slot population in gameplay.
- Emit a shader warmup summary during startup so hardware runs can prove whether stutter remains after full shader warmup.

## Release evidence interpretation for first-use hitches

- If `shader_preset_warmup_complete=1` and `shader_warmup_compiled_count` is high, remaining first-use hitches should be investigated as texture upload, resource traversal, audio bank/sample decode, or display-list path work rather than generic shader compilation.
- If `shader_manifest_entries` approaches `shader_manifest_capacity`, increase capacity or reduce duplicate shader IDs before relying on the manifest as complete coverage.
- If `paletted_manifest_pairs_warmed` is high and `paletted_heuristic_pairs_warmed` remains high too, promote the heuristic discoveries into the durable overlay or generator rules so heuristic fallback is no longer doing normal release work.
- If second-lap smoothness improves but first clean launch still hitches, the release candidate has a packaging/warmup persistence problem, not an acceptable runtime profile.

## Audio preload policy

- Loading raw `sound/*` resources is not enough if the game layer still lazily resolves bank and sequence tables at race boundaries.
- Warm game-facing bank and sequence lookup tables during the same startup preload phase used for textures and shaders.
- Record warmed bank/sequence counts and audio warmup timing so supervised runs can separate audio warmup failures from graphics warmup failures.

## Presentation scale policy

- A fixed half-resolution render scale is preferable to one-third scale if hardware can hold frame time, because it maps cleanly to Vita's 960x544 output and improves text/image clarity.
- Do not ship dynamic quality profiles; if half scale cannot hold 60 fps after warmup fixes, optimize the renderer/preload path before lowering the release target.
