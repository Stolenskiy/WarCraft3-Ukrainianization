#!/usr/bin/env python3
"""Extract / patch string entries in WC3 .fdf string-list files.

An entry line looks like:

    KEY_CAMPAIGN          "Кампании",

We capture the leading whitespace + id verbatim so a patched file keeps the
Russian original's byte layout except for the quoted value.  Values may carry
a trailing comma and an inline comment; both are preserved.

Usage:
  fdf_strings.py extract FILE OUT.json
  fdf_strings.py patch FILE MAP.json OUT.fdf     # MAP: id -> new value
"""

import json
import re
import sys

ENTRY_RE = re.compile(
    r'^(?P<lead>\s*)(?P<id>[A-Za-z0-9_]+)(?P<mid>\s+)(?P<quote>")'
    r"(?P<value>.*)(?P<close>\")(?P<tail>,?\s*)(?P<comment>.*)$"
)


def entries(text):
    """Yield (line_index, id, value) for every string entry line."""
    for i, line in enumerate(text.splitlines()):
        m = ENTRY_RE.match(line)
        if m:
            yield i, m.group("id"), m.group("value")


def load(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    bom = raw.startswith(b"\xef\xbb\xbf")
    crlf = b"\r\n" in raw
    text = raw.decode("utf-8-sig")
    return {"raw": raw, "bom": bom, "crlf": crlf, "text": text}


def extract(path):
    data = load(path)
    out = []
    for i, ident, value in entries(data["text"]):
        out.append({"line": i + 1, "id": ident, "value": value})
    return {"bom": data["bom"], "crlf": data["crlf"], "entries": out}


def patch(path, mapping, out_path):
    data = load(path)
    text = data["text"]
    if data["crlf"]:
        # normalise to \n while editing; restore CRLF on write
        text = text.replace("\r\n", "\n")
    trailing_nl = text.endswith("\n")
    lines = text[:-1].split("\n") if trailing_nl else text.split("\n")
    used = set()
    for i, line in enumerate(lines):
        m = ENTRY_RE.match(line)
        if not m:
            continue
        ident = m.group("id")
        if ident not in mapping:
            continue
        new_val = mapping[ident]
        used.add(ident)
        lines[i] = (
            m.group("lead") + ident + m.group("mid") + '"'
            + new_val + '"' + m.group("tail") + m.group("comment")
        )
    text = "\n".join(lines) + ("\n" if trailing_nl else "")
    raw = text.encode("utf-8")
    if data["crlf"]:
        raw = raw.replace(b"\n", b"\r\n")
    if data["bom"]:
        raw = b"\xef\xbb\xbf" + raw
    with open(out_path, "wb") as fh:
        fh.write(raw)
    return used


def main(argv):
    cmd = argv[1]
    if cmd == "extract":
        data = extract(argv[2])
        with open(argv[3], "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)
        print(f"{len(data['entries'])} entries, bom={data['bom']} crlf={data['crlf']}")
    elif cmd == "patch":
        with open(argv[3], encoding="utf-8") as fh:
            mapping = json.load(fh)
        used = patch(argv[2], mapping, argv[4])
        missing = sorted(set(mapping) - used)
        print(f"patched {len(used)} entries; {len(missing)} mapping ids not found")
        if missing:
            print("missing:", ", ".join(missing[:40]))
    else:
        raise SystemExit(f"unknown command {cmd}")


if __name__ == "__main__":
    main(sys.argv)
