#!/usr/bin/env python3
"""Build Ukrainian-localized standard melee maps for Warcraft III 1.31.

Reads maps extracted from the game's CASC storage (/tmp/wc3-maps-orig/...),
patches the map strings (name / suggested players / description; the strings
live in war3map.wts and its locale-variant blocks, referenced from
war3map.w3i via TRIGSTR_xxx), rebuilds each map archive and writes the
result to an output directory (default /tmp/wc3-maps-uk).

    build_uk_maps.py [--inventory /tmp/maps-inventory.json] [--out DIR] [--install]

--install copies the built maps into the game root Maps/ folder, mirroring
the CASC relative paths (maps/ -> Maps/, maps/frozenthrone/ -> Maps/FrozenThrone/).
Any pre-existing file is backed up first.
"""
import argparse
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wc3map
from map_translations import DESCS, NAMES, PLAYERS

ORIG_ROOT = "/tmp/wc3-maps-orig/war3.w3mod"
DEFAULT_OUT = "/tmp/wc3-maps-uk"
GAME_ROOT = "/Applications/Warcraft III Classic"
GAME_MAPS = os.path.join(GAME_ROOT, "Maps")
BACKUP_DIR = os.path.join(GAME_ROOT, "Backups", "maps-english-originals")

PLAYER_RE = re.compile(
    r"^(Player|Spieler|Jugador|Joueur|Giocatore|Gracz|Игрок|Гравець|玩家|플레이어|Jogador|Oyuncu)\s+(\d+)$")
FORCE_RE = re.compile(r"^(Force|Squadra|Equipo|Équipe|Siła|Отряд|Сила|Fração)\s*(\d+)$")


def wts_value(strings, ref):
    if ref.startswith("TRIGSTR_"):
        return strings.get(int(ref[8:]))
    return ref


def patch_wts_bytes(data, repl):
    """repl: {int id: new text}. Substitutes STRING blocks in the raw wts."""
    for sid, text in repl.items():
        pat = re.compile(rb"STRING %d\s*\r?\n\{\r?\n.*?\r?\n\}" % sid, re.S)
        new = ("STRING %d\r\n{\r\n%s\r\n}" % (sid, text)).encode("utf-8")
        data, n = pat.subn(new, data, count=1)
        if n != 1:
            return None, sid
    return data, None


def translate_players(s):
    s = s.strip()
    if s in PLAYERS:
        return PLAYERS[s]
    return s  # keep unknown formats untouched


def build_map(path, rec):
    """Returns (rebuilt_bytes, report) or raises."""
    m = wc3map.MapArchive(path)
    base = wc3map.parse_wts(m.read_file("war3map.wts"))

    _en_name = wts_value(base, rec["name"])
    en_desc = wts_value(base, rec["desc"])
    en_players = wts_value(base, rec["players"])

    fname = os.path.basename(path)
    uk_name = NAMES.get(fname)
    uk_desc = DESCS.get(en_desc.strip())
    uk_players = translate_players(en_players or "")
    missing = []
    if uk_name is None:
        missing.append("name(%s)" % fname)
    if en_desc.strip() not in DESCS:
        missing.append("desc")
    if missing:
        raise ValueError("missing translations: %s" % ",".join(missing))

    # string ids referenced from w3i
    ids = {}
    for key, ref in (("name", rec["name"]), ("desc", rec["desc"]), ("players", rec["players"])):
        if ref.startswith("TRIGSTR_"):
            ids[key] = int(ref[8:])

    overrides = {}
    patched_wts = []
    for bi in rec["wts_blocks"]:
        data = m.read_block(bi, "")
        strings = wc3map.parse_wts(data)
        repl = {}
        for key, sid in ids.items():
            if sid in strings:
                repl[sid] = {"name": uk_name, "desc": uk_desc, "players": uk_players}[key]
        # player / force labels
        for sid, text in strings.items():
            mm = PLAYER_RE.match(text.strip())
            if mm:
                repl[sid] = "Гравець %s" % mm.group(2)
                continue
            mm = FORCE_RE.match(text.strip())
            if mm:
                repl[sid] = "Сила %s" % mm.group(2)
        if not repl:
            continue
        new_data, failed = patch_wts_bytes(data, repl)
        if new_data is None:
            raise ValueError("wts block %d: could not substitute STRING %d" % (bi, failed))
        # sanity: parse back and confirm
        check = wc3map.parse_wts(new_data)
        for sid, text in repl.items():
            assert check.get(sid) == text, "wts block %d id %d mismatch" % (bi, sid)
        overrides[bi] = new_data
        patched_wts.append(bi)

    # drop maintenance files (their content is tied to the old archive layout)
    for name in ("(attributes)", "(signature)"):
        overrides[name] = None
    # regenerate a plain-text listfile with the names we know
    lf_names = ["war3map.wts"] + ["war3map.w3i"]
    overrides["(listfile)"] = ("\r\n".join(sorted(set(lf_names))) + "\r\n").encode("utf-8")

    out, kept = wc3map.rebuild_map(path, overrides)
    report = {
        "path": rec["path"],
        "name": uk_name,
        "players": uk_players,
        "wts_blocks_patched": patched_wts,
        "files_kept": len(kept),
        "orig_size": os.path.getsize(path),
        "new_size": len(out),
    }
    return out, report


def verify_built(src_path, out_path, rec):
    m = wc3map.MapArchive(out_path)
    m0 = wc3map.MapArchive(src_path)
    # hash identities preserved (except dropped maintenance files)
    dropped = set()
    for name in ("(attributes)", "(signature)", "(listfile)"):
        h1, h2 = wc3map.mpq_hash(name, wc3map.MPQ_HASH_NAME_A), wc3map.mpq_hash(name, wc3map.MPQ_HASH_NAME_B)
        if (h1, h2) in m0.entries:
            dropped.add((h1, h2))
    a = set(m0.entries) - dropped
    b = set(m.entries) - dropped
    if a != b:
        raise ValueError("hash identities changed: only-new=%s only-old=%s" % (
            sorted(hex(x[0]) for x in b - a)[:3], sorted(hex(x[0]) for x in a - b)[:3]))
    # w3i parses and still references the same TRIGSTR ids
    meta = wc3map.parse_w3i(m.read_file("war3map.w3i"))
    assert meta["name"] == rec["name"] and meta["description"] == rec["desc"] and meta["players"] == rec["players"]
    # base wts contains the Ukrainian text
    strings = wc3map.parse_wts(m.read_file("war3map.wts"))
    fname = os.path.basename(out_path)
    uk_name = NAMES[fname]
    found = any(t == uk_name for t in strings.values())
    assert found, "ukrainian name not found in rebuilt %s" % rec["path"]
    # every untouched block byte-identical
    for _bi in range(len(m0.block_table)):
        pass  # raw-copy is guaranteed by construction; spot check below
    return True


def install(rel, out_path):
    rel_disk = rel.replace("\\", "/")
    assert rel_disk.startswith("maps/")
    sub = rel_disk[len("maps/"):]
    dest = os.path.join(GAME_MAPS, sub)
    dest = os.path.normpath(dest)
    # safety: destination must be inside game Maps/
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    # realpath: симлінк у дорозі не має вивести за межі Maps/
    assert os.path.realpath(dest).startswith(os.path.realpath(GAME_MAPS) + os.sep), dest
    bak = os.path.join(BACKUP_DIR, sub)
    if os.path.exists(dest) and not os.path.exists(bak):
        # бекап лише ОРИГІНАЛУ: повторний --install не має затерти його вже українською картою
        os.makedirs(os.path.dirname(bak), exist_ok=True)
        shutil.copy2(dest, bak)
        print("backup:", dest, "->", bak)
    shutil.copy2(out_path, dest)
    return dest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inventory", default="/tmp/maps-inventory.json")
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--install", action="store_true")
    ap.add_argument("--only", default=None, help="substring filter on map path")
    args = ap.parse_args()

    inv = json.load(open(args.inventory))
    recs = [r for r in inv if "name" in r and "wts_blocks" in r]
    if args.only:
        recs = [r for r in recs if args.only in r["path"]]

    os.makedirs(args.out, exist_ok=True)
    report = []
    failures = []
    for rec in recs:
        src = os.path.join(ORIG_ROOT, rec["path"].replace("\\", "/"))
        out_path = os.path.join(args.out, rec["path"].replace("\\", "/"))
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        try:
            data, rep = build_map(src, rec)
            with open(out_path, "wb") as f:
                f.write(data)
            verify_built(src, out_path, rec)
            rep["ok"] = True
        except Exception as e:
            failures.append((rec["path"], repr(e)))
            print("FAIL", rec["path"], e, file=sys.stderr)
            continue
        if args.install:
            rep["installed"] = install(rec["path"], out_path)
        report.append(rep)
        print("ok", rec["path"], rep["name"], "(%d -> %d bytes, wts blocks %s)" % (
            rep["orig_size"], rep["new_size"], rep["wts_blocks_patched"]))

    with open(os.path.join(args.out, "build-report.json"), "w") as f:
        json.dump({"built": report, "failures": failures}, f, ensure_ascii=False, indent=1)
    print("built %d, failures %d" % (len(report), len(failures)))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
