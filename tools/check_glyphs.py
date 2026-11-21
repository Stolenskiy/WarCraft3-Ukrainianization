#!/usr/bin/env python3
"""Check that TTF fonts cover every character used in a set of string files.

Usage: check_glyphs.py FONT [FONT...] STRINGS_JSON [STRINGS_JSON...]

Each STRINGS_JSON is the output of fdf_strings.py extract (a JSON object with
an "entries" list).  Reports, per font, the set of uncovered codepoints.
"""

import json
import string
import sys

BASE = set(string.printable)


def _parse_format4_lenient(data, base, chars):
    """Tolerant format-4 parse: game fonts (e.g. dfheimd.ttf) carry subtables
    fontTools rejects (idRangeOffset at the very end of the array)."""
    import struct
    fmt, length, _lang, segX2 = struct.unpack_from(">HHHH", data, base)
    if fmt != 4:
        return False
    seg = segX2 // 2
    end_off = base + 14
    start_off = end_off + segX2 + 2
    delta_off = start_off + segX2
    range_off = delta_off + segX2
    ends = struct.unpack_from(f">{seg}H", data, end_off)
    starts = struct.unpack_from(f">{seg}H", data, start_off)
    deltas = struct.unpack_from(f">{seg}H", data, delta_off)
    try:
        ranges = struct.unpack_from(f">{seg}H", data, range_off)
    except struct.error:
        ranges = [0] * seg
    limit = min(length, len(data) - base)
    for i in range(seg):
        if ranges[i] == 0:
            for cp in range(starts[i], min(ends[i], 0xFFFF) + 1):
                chars.add(cp)
        else:
            for cp in range(starts[i], min(ends[i], 0xFFFF) + 1):
                # glyphIndexArray entry is addressed relative to &idRangeOffset[i]
                abs_off = range_off + 2 * i + ranges[i] + (cp - starts[i]) * 2
                if abs_off + 2 <= len(data):
                    g = struct.unpack_from(">H", data, abs_off)[0]
                else:
                    g = 0
                if g != 0:
                    chars.add(cp)
    return True


def _parse_format12_lenient(data, base, chars):
    import struct
    fmt, _res, length = struct.unpack_from(">HHI", data, base)
    if fmt != 12:
        return False
    n = struct.unpack_from(">I", data, base + 12)[0]
    off = base + 16
    for i in range(n):
        try:
            sc, ec, sg = struct.unpack_from(">III", data, off + 12 * i)
        except struct.error:
            break
        if sc <= 0x10FFFF:
            chars.update(range(sc, min(ec, 0x10FFFF) + 1))
    return True


def cmap_of(path):
    """Parse the cmap table directly from file bytes.  Game fonts (dfheimd.ttf,
    dffn_b31.ttf) carry subtables fontTools refuses to decompile, so we read
    formats 4 and 12 ourselves, tolerantly."""
    import struct
    with open(path, "rb") as fh:
        raw = fh.read()
    # locate the cmap table via the table directory
    num_tables = struct.unpack_from(">H", raw, 4)[0]
    cmap_off = None
    for i in range(num_tables):
        rec = 12 + 16 * i
        tag = raw[rec:rec + 4]
        off = struct.unpack_from(">I", raw, rec + 8)[0]
        if tag == b"cmap":
            cmap_off = off
            break
    if cmap_off is None:
        raise SystemExit(f"{path}: no cmap table")
    chars = set()
    ver, n = struct.unpack_from(">HH", raw, cmap_off)
    for i in range(n):
        rec = cmap_off + 4 + 8 * i
        sub_off = struct.unpack_from(">I", raw, rec + 4)[0]
        base = cmap_off + sub_off
        if base + 4 > len(raw):
            continue
        fmt = struct.unpack_from(">H", raw, base)[0]
        if fmt == 4:
            _parse_format4_lenient(raw, base, chars)
        elif fmt == 12:
            _parse_format12_lenient(raw, base, chars)
        elif fmt in (0, 6):
            try:
                if fmt == 0:
                    chars.update(raw[base + 6:base + 6 + 256])
                else:
                    first, cnt = struct.unpack_from(">HH", raw, base + 6)
                    chars.update(range(first, first + cnt))
            except Exception:
                pass
    return chars


def main(argv):
    args = argv[1:]
    fonts = [a for a in args if not a.endswith(".json")]
    strings = [a for a in args if a.endswith(".json")]
    cmaps = {f: cmap_of(f) for f in fonts}
    missing = {}
    for path in strings:
        data = json.load(open(path))
        for e in data["entries"]:
            for ch in e["value"]:
                if ch in BASE:
                    continue
                for f, cm in cmaps.items():
                    if ord(ch) not in cm:
                        missing.setdefault(f, set()).add(ch)
    ok = True
    for f in fonts:
        miss = missing.get(f, set())
        if miss:
            ok = False
            print(f"{f}: MISSING {len(miss)}: " + " ".join(
                f"U+{ord(c):04X}({c})" for c in sorted(miss, key=ord)))
        else:
            print(f"{f}: full coverage")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main(sys.argv)
