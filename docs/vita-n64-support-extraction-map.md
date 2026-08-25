# Vita/N64 support extraction map

This map identifies the current Vita Kart 64 work that should become reusable infrastructure after the port passes supervised hardware release gates.

Do not extract this package before Vita Kart 64 stabilizes. The reference implementation should prove the patterns on real PS Vita hardware first.

## Candidate package name

```text
vita-n64-support
```

## Current project-owned inputs

These values should remain project-specific parameters:

1. Product name: `Vita Kart 64`
2. Title ID: `VITAKRT64`
3. Data directory: `ux0:data/vitakart64`
4. Archive name: `mk64-vita.o2r`
5. Texture-pair manifest: `assets/vita/texture-pairs.manifest`
6. Texture-pair overlay: `assets/vita/texture-pairs-extra.manifest`
7. Shader seed manifest: `assets/vita/shader-manifest.txt`
8. Build command: `tools/vita_prepare_supervised_release.sh`
9. Release gate manifest: `docs/vita-kart-64-release-gates.json`

## Reusable script candidates

### Build/deploy guards

Candidate reusable files:

1. `tools/vita_require_supervised_hardware_run.sh`
2. `tools/vita_deploy_release.sh`
3. `tools/vita_build_install_stopped.sh`
4. `tools/vita_prepare_supervised_release.sh`

Required parameterization:

1. project root
2. title ID
3. VPK path
4. Vita data directory
5. deploy/install command
6. whether vendor-library rebuild is required

### Archive/resource analysis

Candidate reusable files:

1. `tools/vita_generate_texture_pairs.py`
2. `tools/vita_texture_manifest_stats.py`
3. `tools/vita_audit_texture_pair_coverage.py`
4. `tools/vita_audit_archive_layout.py`
5. `tools/vita_plan_resource_warmup.py`
6. `tools/vita_plan_cache_phases.py`

Required parameterization:

1. archive path
2. resource namespace prefixes
3. texture metadata parser
4. palette/TLUT pairing rules
5. expected texture formats
6. memory budget thresholds

### Runtime cache/evidence tools

Candidate reusable files:

1. `tools/vita_collect_runtime_cache.py`
2. `tools/vita_merge_shader_manifest.py`
3. `tools/vita_merge_texture_misses.py`
4. `tools/vita_compare_runtime_cache.py`
5. `tools/vita_summarize_frame_hitches.py`
6. `tools/vita_apply_preload_summary_to_report.py`
7. `tools/vita_pull_latest_crash.py`

Required parameterization:

1. remote Vita cache paths
2. local cache directory
3. manifest paths
4. crash search directories
5. report format
6. diagnostic log filenames

### Release-gate workflow

Candidate reusable files:

1. `tools/vita_generate_release_gate_checklist.py`
2. `tools/vita_score_release_gate_checklist.py`
3. `tools/vita_triage_supervised_run.py`
4. `tools/vita_bundle_supervised_evidence.py`
5. `tools/vita_hash_release_gates.py`
6. `tools/vita_print_morning_run_plan.sh`
7. `tools/vita_print_unattended_hold_status.sh`

Required parameterization:

1. release-gate JSON path
2. report output directory
3. evidence bundle file list
4. gate IDs
5. diagnostic decision tree
6. supervised operator assumptions

## Reusable runtime-code candidates

### Boot/performance policy

Candidate current area:

```text
src/port/VitaPlatform.cpp
```

Reusable behavior:

1. max-clock setup
2. rendering CVar reassertion after config load
3. release diagnostic reset
4. frame-hitch logging behind compile-time flags
5. app termination cleanup

Game-specific behavior to keep outside support package:

1. product paths
2. game-specific CVar names unless wrapped behind adapters
3. report copy that names Vita Kart 64

### Loading UX

Candidate current area:

```text
src/port/VitaLoadingScreen.cpp
```

Reusable behavior:

1. full-screen progress layout
2. elapsed-time display
3. estimated-time display
4. wrapped status text
5. fallback N64-style badge
6. phase/resource/GPU/cache status fields

Game-specific behavior to keep outside support package:

1. product title text
2. artwork
3. exact copy
4. any game-branded color decisions

### Resource preload and warmup

Candidate current area:

```text
src/port/VitaPreload.cpp
libultraship/src/fast/interpreter.cpp
libultraship/include/fast/interpreter.h
```

Reusable behavior:

1. archive resource grouping
2. preload summary counters
3. CI/TLUT pair loading
4. native RGBA5551 upload attempt
5. shader preset warmup
6. app-local plus Vita-local manifest loading

Game-specific behavior to keep outside support package:

1. MK64 resource names
2. MK64-specific texture/TLUT naming heuristics
3. game-specific deferred-resource choices

### Renderer backend policy

Candidate current area:

```text
libultraship/src/fast/backends/gfx_opengl.cpp
libultraship/include/fast/backends/gfx_opengl.h
libultraship/include/fast/backends/gfx_rendering_api.h
```

Reusable behavior:

1. texture-slot reservation hook
2. native RGBA16/RGBA5551 upload hook
3. texture binding invalidation hook
4. sampler-state cache
5. reserved texture ID pool
6. exact fullscreen viewport/scissor clamp

Game-specific behavior to keep outside support package:

1. anything that depends on MK64 scenes
2. any hard-coded title-specific diagnostic path

## Extraction order

1. Finish Vita Kart 64 release candidate on hardware.
2. Freeze the passing artifact and evidence bundle.
3. Copy script candidates into `vita-n64-support/tools`.
4. Replace hard-coded paths/title IDs with a config file.
5. Create a minimal integration guide for boot, preload, renderer, and evidence hooks.
6. Port one second decomp project using the support package to prove it is not overfit to MK64.

## Reuse contract

A future port should be able to adopt the support package by providing:

1. title metadata
2. build/deploy commands
3. archive path
4. data directory
5. resource metadata parser
6. texture/TLUT pairing rules
7. loading-screen title/artwork
8. release-gate JSON
9. hardware-run checklist expectations

The support package should provide the rest: supervised guards, cache/warmup tooling, evidence generation, crash/cache collection helpers, and the release-gate workflow.

