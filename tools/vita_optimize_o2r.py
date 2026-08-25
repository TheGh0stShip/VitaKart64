#!/usr/bin/env python3
"""Create a Vita runtime O2R with every entry stored for deterministic reads."""

from __future__ import annotations

import argparse
import copy
import os
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile


def optimize(source: Path, destination: Path) -> None:
    source = source.resolve()
    destination = destination.resolve()
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.unlink(missing_ok=True)

    entry_count = 0
    raw_bytes = 0
    with ZipFile(source, "r") as src, ZipFile(temporary, "w", allowZip64=True) as dst:
        dst.comment = src.comment
        for info in src.infolist():
            data = src.read(info)
            stored = copy.copy(info)
            stored.compress_type = ZIP_STORED
            stored._compresslevel = None
            dst.writestr(stored, data)
            entry_count += 1
            raw_bytes += len(data)

    os.replace(temporary, destination)
    print(f"Stored {entry_count} resources ({raw_bytes} bytes) in {destination.name}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", nargs="?", type=Path, default=Path("mk64.o2r"))
    parser.add_argument("destination", nargs="?", type=Path, default=Path("mk64-vita.o2r"))
    args = parser.parse_args()
    optimize(args.source, args.destination)


if __name__ == "__main__":
    main()
