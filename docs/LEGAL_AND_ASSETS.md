# Legal and asset policy

## What is allowed in this repository

- Source code, build scripts, release scripts, and documentation.
- Generic Vita Kart 64 brand/loading assets created for this port.
- Text manifests that describe runtime warmup behavior.
- Compatibility patches for open-source dependencies.

## What must stay local

- ROM files: `.z64`, `.n64`, `.v64`.
- Generated game archives: `.o2r`, `.otr`.
- VPKs, ELFs, SELF/FSELF binaries, `eboot.bin`, and `param.sfo` unless all included assets are cleared for distribution.
- Crash dumps and private hardware-run data.
- Any file extracted directly from a copyrighted ROM.

## User-supplied ROM

Builders must use their own legally obtained US Mario Kart 64 ROM dump. The supported SHA-1 is:

```text
579C48E211AE952530FFC8738709F078D5DD215E
```

## Public binary releases

A public VPK should not be published from this repo unless a separate legal review confirms that every packed asset is distributable. The default release process therefore publishes source/tooling archives only.
