# Vita Kart 64 v0.1.0 source/tooling

Initial public source/tooling release for the PS Vita-focused Vita Kart 64 port.

## Included

- Vita Makefile build path for `VITAKRT64`.
- Max-performance Vita policy targeting ARM 500 MHz, BUS 222 MHz, GPU 222 MHz, XBAR 166 MHz.
- Custom Vita Kart loading/LiveArea asset generation flow.
- vitaGL vendor build script with shader cache, scratch memory, sampler speedhack, no-debug, and no-splash policy.
- Deterministic O2R storage conversion tool for Vita runtime archives.
- Shader/resource warmup manifests, runtime cache promotion tools, and supervised hardware triage scripts.
- Release gate manifest, setup docs, asset/legal policy, and N64-to-Vita porting notes.

## Not included

- No ROM.
- No generated `.o2r` archives.
- No `.vpk`, `eboot.bin`, ELF/SELF binaries, crash dumps, or private hardware evidence.

Builders must provide their own legally obtained US Mario Kart 64 ROM and generate local archives before building a VPK.
