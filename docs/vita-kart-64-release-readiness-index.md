# Vita Kart 64 release-readiness index

This is the single entry point for the next supervised hardware pass. It does not replace the full docs; it points to the exact artifacts needed to decide whether the next build is a release candidate.

## Current unattended state

hardware tester is asleep. Do not build, install, launch, use Vita3K, contact the PS Vita, pull crashes, harvest runtime caches, or run validation.

Allowed unattended work is limited to local source edits, offline tooling edits, documentation, and research that does not require immediate runtime proof.

## Awake supervised build command

Run only when hardware tester is awake:

```sh
cd <repo-root>
VITAKART_SUPERVISED_HARDWARE_RUN=1 tools/vita_prepare_supervised_release.sh
```

Expected behavior:

1. Confirm supervised hardware intent.
2. Generate `hardware-runs/next-supervised-checklist.md`.
3. Generate `hardware-runs/release-gate-digest.txt`.
4. Enforce vitaGL release policy.
5. Regenerate stale texture-pair warmup manifests.
6. Build the release VPK.
7. Write release evidence.
8. Create a hardware-run report.
9. Install/deploy to the PS Vita stopped.
10. Do not launch the app automatically.

## Manual hardware run gates

The next PS Vita hardware run must prove:

1. Custom loading screen appears instead of middleware/vitaGL splash.
2. Loading screen reports useful progress and completes.
3. Audio works from boot/menu through race and post-race.
4. First race start has no visible first-use hitch.
5. Raceplay is locked 60 fps on the configured OC profile.
6. Post-race score screen is smooth on first entry.
7. Right and bottom presentation edges are clean.
8. Image and text quality are acceptable under locked-60 policy.

## After-run tools

Use only after the supervised hardware pass exists:

```sh
tools/vita_score_release_gate_checklist.py hardware-runs/next-supervised-checklist.md
tools/vita_triage_supervised_run.py
tools/vita_bundle_supervised_evidence.py
```

Use cache/crash collection scripts only when hardware tester is awake and only if the run produced data that needs collection.

## Key local docs

1. `docs/vita-kart-64-release-gates.json`: canonical release gates.
2. `docs/vita-release-gate-schema.md`: release-gate JSON contract.
3. `docs/next-supervised-vita-run.md`: detailed next-run procedure.
4. `docs/next-supervised-build-change-log.md`: changes queued for the next build.
5. `docs/unattended-work-handoff.md`: current sleep-window handoff.
6. `docs/vita-kart-64-polish-backlog.md`: ordered polish and blocker backlog.
7. `docs/vita-n64-support-package-architecture.md`: reusable support-package design.
8. `docs/vita-n64-support-extraction-map.md`: current-file extraction map.

## Decision after the next run

If every gate passes:

1. Score the filled checklist.
2. Bundle evidence.
3. Treat the artifact as the current release candidate.

If hitches remain:

1. Check preload summary first.
2. If texture misses exist, merge only supervised hardware-discovered pairs.
3. If no texture misses exist, use one supervised frame-hitch diagnostic build.
4. If hitches localize to post-race, add a post-race preload phase before renderer changes.

If presentation artifacts return:

1. Freeze performance and image-quality changes.
2. Fix viewport/scissor/framebuffer presentation policy first.

If audio fails:

1. Fix audio output/setup before frame-pacing or image-quality work.

If image quality is the only failed gate:

1. Explore selective UI/text filtering first.
2. Avoid heavier antialiasing unless hardware frame-time headroom is proven.


## Brand identity gate update

The next supervised run must also prove the Vita Kart 64 identity assets:

1. `livearea-indexed/icon0.png` is packaged/displayed as the app icon where applicable.
2. `livearea-indexed/startup.png` is packaged/displayed as the startup/LiveArea card where applicable.
3. `assets/vita/loading.png` appears as the custom loading card instead of middleware splash.
4. `assets/vita/brand-assets.manifest.json` is generated during the supervised wrapper flow and captured in release evidence.
5. The branding is project-specific but does not look like official Nintendo/Sony branding.

## Warmup persistence gate update

The next supervised pass must include a close/reopen check:

1. Launch once and reach gameplay/post-race evidence path.
2. Confirm `preload-ready.marker` is collected after successful preload.
3. Close the app normally.
4. Reopen on PS Vita hardware.
5. Confirm first-exposure hitches do not return on the second launch.
6. Mark `warmup_persistence` in the checklist based on hardware behavior and preload marker evidence.

## 2026-08-25 overnight local candidate updates

- Fixed render scale is now `1/2`; visual-quality gate must confirm cleaner text/image presentation while race/post-race remains locked 60 fps.
- Shader warmup now records `shader-warmup-summary.txt`, uses full-width shader IDs, warms combiner cache entries, and covers all 16 clamp-mode slots in the preset matrix.
- Runtime preload now warms audio bank/sequence tables and records audio warmup counters/timing.
- Presentation blits now snap near-fullscreen Vita destination rectangles to 960x544 to target right/bottom retained-frame artifacts.
- Post-run workflow now separates cache harvest, promotion preview, optional seed promotion, optional latest-crash pull, and triage into one supervised wrapper.

None of these updates are release-proven until hardware tester runs the next supervised PS Vita hardware pass.
