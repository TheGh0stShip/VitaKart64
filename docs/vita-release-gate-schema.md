# Vita release-gate schema

This schema describes `docs/vita-kart-64-release-gates.json` and the reusable release-gate format for future PS Vita/N64 decomp ports.

The JSON file is the canonical local definition of what must be proven during a supervised hardware run. It is not proof by itself.

## Top-level fields

### `product`

Type: string

Human-readable product name.

Example:

```json
"Vita Kart 64"
```

### `platform`

Type: string

Hardware target. For Vita Kart 64 this must describe real PS Vita hardware, not Vita3K.

Example:

```json
"PS Vita hardware"
```

### `supervised_only`

Type: boolean

When true, the project requires an awake operator for build/install/run evidence and must not claim release status from unattended actions.

### `release_build_command`

Type: string

The canonical command for producing the next candidate build. It should install stopped and must not launch the app by itself.

### `launch_policy`

Type: string

Expected deployment behavior.

Required value for Vita Kart 64:

```json
"install_stopped_then_manual_launch"
```

## `target`

Type: object

Required numeric fields:

1. `fps`
2. `arm_mhz`
3. `bus_mhz`
4. `gpu_mhz`
5. `xbar_mhz`

Vita Kart 64 release target:

```json
{
  "fps": 60,
  "arm_mhz": 500,
  "bus_mhz": 222,
  "gpu_mhz": 222,
  "xbar_mhz": 166
}
```

## `required_build_policy`

Type: object

Build-time or packaging policies that must be true for a candidate artifact.

Expected Vita Kart 64 fields:

1. `full_ci_tlut_coverage`
2. `texture_pair_limit`
3. `texture_miss_log_release`
4. `frame_hitch_log_release`
5. `middleware_splash`

The checklist generator treats each key as a build-policy gate. A filled checklist must mark each build-policy gate as `PASS`.

## `required_runtime_gates`

Type: array of objects

Each gate object requires:

1. `id`: stable snake-case identifier.
2. `evidence`: the evidence class expected for the gate.
3. `pass`: the human-readable passing condition.

Vita Kart 64 required runtime gate IDs:

1. `loading_screen`
2. `audio`
3. `race_start_hitch`
4. `race_fps`
5. `post_race_scoreboard`
6. `presentation_edges`
7. `visual_quality`

Every runtime gate must be proven on PS Vita hardware before release-candidate status is valid.

## `diagnostic_order_if_failed`

Type: array of strings

Ordered fix-selection guidance for failed supervised runs. This should describe diagnostic sequencing, not execute it.

For Vita Kart 64, diagnostics should prefer:

1. Existing preload summary.
2. One supervised frame-hitch diagnostic build if hitches remain unexplained.
3. Texture/TLUT overlay merge only when supervised misses prove coverage gaps.
4. Presentation fixes before performance changes if edge artifacts return.

## Status vocabulary

Filled checklists should use exactly one of:

1. `PASS`
2. `FAIL`
3. `NOT TESTED`

Generated worksheets may show all three as placeholders. The operator should replace the placeholder with exactly one status before scoring.

## Portability notes

Future N64/Vita ports should reuse the same top-level structure but replace project-specific values:

1. `product`
2. `release_build_command`
3. data paths referenced by local tooling
4. runtime gate IDs if the port has different required screens or subsystems

The invariant stays the same: no release-candidate claim without supervised real-hardware evidence.


## Vita Kart 64 brand-gate extension

Vita Kart 64 now adds two build-policy fields:

1. `brand_assets_generated`: expected `true` when deterministic local generators produce the packaged loading, startup, and icon PNGs.
2. `brand_asset_manifest`: expected `true` when `assets/vita/brand-assets.manifest.json` exists and records hashes for generated brand assets and generator sources.

Vita Kart 64 also adds runtime gate ID:

1. `brand_identity`: proves on PS Vita hardware and release evidence that the Vita Kart 64 icon, LiveArea/startup art, and loading-card identity are packaged and visible without official-looking Nintendo/Sony branding.

The release-gate digest will change because the manifest changed. Let `tools/vita_prepare_supervised_release.sh` regenerate `hardware-runs/release-gate-digest.txt` during the next supervised build flow.

## Checklist status-field update

Generated checklists now use a single explicit field per gate:

```text
status: ____
```

hardware tester should replace the blank with exactly one value: `PASS`, `FAIL`, or `NOT TESTED`. The checklist scorer and supervised-run triage helper now prefer this explicit field and treat blanks as `NOT TESTED`.

This avoids ambiguity from older placeholder text such as `PASS / FAIL / NOT TESTED` appearing on the same line.

## Warmup persistence gate extension

Vita Kart 64 now includes runtime gate ID:

1. `warmup_persistence`: after closing and reopening the app on PS Vita hardware, preload-ready marker evidence must exist and the second launch must not reintroduce first-exposure shader/resource hitches.

This gate exists because warmup/caching behavior must survive normal user close/reopen behavior, not only become smooth after repeated exposure in a single process lifetime.

## 2026-08-25 render and warmup evidence extensions

- `target.fixed_render_scale` records the release render scale; Vita Kart 64 currently targets `1/2`.
- `target.dynamic_performance_profiles` must remain `false` for the requested single max-performance profile.
- Runtime gates may require structured preload evidence, including `shader-warmup-summary.txt`, `preload-summary.txt`, and `preload-ready.marker` fields.
- Audio readiness should include both subjective audio presence and preload counters for warmed banks/sequences.
- Warmup persistence should be judged on a clean close/reopen hardware run, not on a smoother second lap within one process lifetime.
