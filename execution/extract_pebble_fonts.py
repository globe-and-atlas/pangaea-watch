#!/usr/bin/env python3
"""
execution/extract_pebble_fonts.py
Extracts Pebble system font bitmaps (Gothic, LECO) from the local Pebble SDK's Emery emulator
firmware into .tmp/pebble_fonts.json, so the browser preview measures and draws text exactly as
the watch will.

The output stays in .tmp/ (gitignored): these are firmware fonts and their redistribution terms
are unclear, so they are regenerated from each developer's own SDK rather than committed.

Formats: the system resource pack (num_files, crc, timestamp, then 16-byte table entries
id/offset/length/crc, then data) and PBF v3 fonts (10-byte header, codepoint hash table,
offset table, glyphs of [w, h, left, top, advance] + 1-bit LSB-first bitmap).
"""

from __future__ import annotations

import argparse
import base64
import bz2
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = ROOT / ".tmp" / "pebble_fonts.json"
SDK_ROOT = Path.home() / "Library" / "Application Support" / "Pebble SDK" / "SDKs"
FLASH = Path("sdk-core/pebble/emery/qemu/qemu_spi_flash.bin.bz2")

# name -> (resource id, max height, glyph count) fingerprinted against SDK 4.33.1
FONTS = {
    "GOTHIC_14": (44, 14, 371),
    "GOTHIC_14_BOLD": (46, 14, 371),
    "GOTHIC_18": (47, 18, 371),
    "GOTHIC_18_BOLD": (6, 18, 371),
    "GOTHIC_24": (49, 24, 371),
    "GOTHIC_24_BOLD": (50, 24, 371),
    "GOTHIC_28_BOLD": (53, 28, 371),
    "LECO_32_BOLD_NUMBERS": (69, 32, 98),
    "LECO_36_BOLD_NUMBERS": (70, 36, 98),
    "LECO_38_BOLD_NUMBERS": (71, 38, 98),
    "LECO_42_NUMBERS": (72, 42, 98),
}
CODEPOINTS = list(range(32, 127)) + [0xB0, 0xB7, 0x2013, 0x2022, 0x2026]


def find_flash(sdk: Path | None) -> Path:
    candidates = [sdk] if sdk else sorted(SDK_ROOT.glob("*"), reverse=True)
    for c in candidates:
        if c and (c / FLASH).exists():
            return c / FLASH
    raise FileNotFoundError(f"No Emery emulator flash under {SDK_ROOT} (install the Pebble SDK)")


def locate_pack(spi: bytes) -> tuple[int, int, list[tuple[int, int, int]]]:
    """(base, data_start, [(id, offset, length)]) of the system resource pack."""
    for base in range(0, len(spi) - 64, 0x1000):
        n = struct.unpack_from("<I", spi, base)[0]
        if not 50 < n < 4000:
            continue
        entries = [struct.unpack_from("<III", spi, base + 12 + 16 * i) for i in range(n)]
        if any(e[0] != i + 1 for i, e in enumerate(entries[:8])):
            continue
        # The table is padded to a fixed capacity; pick the one where fonts parse
        for cap in (256, 512, 768, 1024, 2048):
            data_start = base + 12 + 16 * cap
            rid, off, _ = entries[FONTS["GOTHIC_14"][0] - 1]
            ver, max_h = spi[data_start + off], spi[data_start + off + 1]
            if ver == 3 and max_h == 14:
                return base, data_start, entries
    raise ValueError("System resource pack not found in emulator flash")


def parse_pbf(data: bytes) -> tuple[int, dict[int, list]]:
    ver, max_h, n, wild, hts, cpb, hdr, features = struct.unpack_from("<BBHHBBBB", data, 0)
    if ver != 3 or features & 2:
        raise ValueError(f"Unsupported PBF (version {ver}, features {features})")
    ent = cpb + (2 if features & 1 else 4)
    offtab = hdr + 4 * hts
    glyph_table = offtab + ent * n
    offsets: dict[int, int] = {}
    for h in range(hts):
        _, count, off = struct.unpack_from("<BBH", data, hdr + 4 * h)
        for k in range(count):
            p = offtab + off + k * ent
            offsets[int.from_bytes(data[p:p + cpb], "little")] = int.from_bytes(data[p + cpb:p + ent], "little")
    glyphs = {}
    for cp in CODEPOINTS:
        go = offsets.get(cp)
        if go is None:
            continue
        p = glyph_table + go  # byte offset into the glyph table
        w, h, left, top, adv = struct.unpack_from("<BBbbb", data, p)
        nbytes = (w * h + 7) // 8
        glyphs[cp] = [w, h, left, top, adv, base64.b64encode(data[p + 5:p + 5 + nbytes]).decode()]
    return max_h, glyphs, n


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk", type=Path, help="Pebble SDK version directory (default: newest)")
    args = parser.parse_args()

    flash = find_flash(args.sdk)
    spi = bz2.decompress(flash.read_bytes())
    base, data_start, entries = locate_pack(spi)
    print(f"→ resource pack at {base:#x}, {len(entries)} resources ({flash.parent.parent.parent.parent.name})")

    fonts = {}
    for name, (rid, want_h, want_n) in FONTS.items():
        _, off, length = entries[rid - 1]
        max_h, glyphs, n = parse_pbf(spi[data_start + off:data_start + off + length])
        if (max_h, n) != (want_h, want_n):
            raise AssertionError(f"{name}: fingerprint {max_h}/{n} != expected {want_h}/{want_n}")
        fonts[name] = {"max_height": max_h, "glyphs": {str(cp): g for cp, g in glyphs.items()}}
        print(f"  {name:22s} h{max_h:2d}  {len(glyphs):3d} glyphs")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps({"source": str(flash), "fonts": fonts}, separators=(",", ":")),
                           encoding="utf-8")
    print(f"→ wrote {OUTPUT_PATH.relative_to(ROOT)} ({OUTPUT_PATH.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
