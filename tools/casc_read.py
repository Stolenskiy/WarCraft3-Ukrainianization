#!/usr/bin/env python3
"""Minimal read-only CASC local-storage reader for Warcraft III 1.31 (w3t).

Reads the game's Data/ folder (.idx indices + data.000/data.001 blobs),
parses the text-format war3 root file, and can extract files by path.

Usage:
    casc_read.py list [--filter MAPS]
    casc_read.py extract --filter "Maps\\" --out DIR
"""
import os
import struct
import sys

from PyCASC.utils.blizzutils import hexkey_to_bytes, var_int
from PyCASC.utils.CASCUtils import parse_blte, parse_encoding_file

GAME_ROOT = os.environ.get("WC3_GAME_ROOT", "/Applications/Warcraft III Classic")
DATA_DIR = os.path.join(GAME_ROOT, "Data")
def _active_build_key(default: str = "9a75938c4606d6393fe0960c4ad5d9d5") -> str:
    """Build Key активної збірки з <гра>/.build.info (інші збірки гри теж працюють)."""
    try:
        with open(os.path.join(GAME_ROOT, ".build.info"), encoding="utf-8") as f:
            lines = [ln.rstrip("\n").split("|") for ln in f if ln.strip()]
        cols = [c.split("!")[0] for c in lines[0]]
        for row in lines[1:]:
            rec = dict(zip(cols, row))
            if rec.get("Active") == "1" and rec.get("Build Key"):
                return rec["Build Key"]
    except (OSError, IndexError):
        pass
    return default


BUILD_KEY = _active_build_key()


def read_config(name):
    path = os.path.join(DATA_DIR, "config", name[:2], name[2:4], name)
    with open(path, "rb") as f:
        return f.read()


def build_idx_index():
    """Map ekey (bytes) -> (data file index, offset, size) from all .idx files."""
    index = {}
    idx_dir = os.path.join(DATA_DIR, "data")
    for fname in sorted(os.listdir(idx_dir)):
        if not fname.endswith(".idx"):
            continue
        path = os.path.join(idx_dir, fname)
        with open(path, "rb") as f:
            hdr = struct.unpack("IIH6BQQII", f.read(0x28))
            ess, eos, eks = hdr[5], hdr[6], hdr[7]
            entry_len = hdr[11]
            f.seek(0x28)
            for _ in range(0, entry_len, ess + eos + eks):
                ek = var_int(f, eks, False)
                eo = var_int(f, eos, False)
                es = var_int(f, ess)
                data_file = eo >> 30
                offset = eo & (2 ** 30 - 1)
                # keys in local .idx are truncated to eks bytes (high-order)
                index.setdefault(ek.to_bytes(eks, "big"), []).append((data_file, offset, es, eks))
    return index


class CASC:
    def __init__(self):
        self.idx = build_idx_index()
        bc = read_config(BUILD_KEY).decode()
        cfg = {}
        for line in bc.splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip()
        self.cfg = cfg
        enc_keys = cfg["encoding"].split()
        # encoding = <CKey> <EKey>; local storage is keyed by EKey
        enc_raw = self.read_ekey(hexkey_to_bytes(enc_keys[1]))
        spec, enc_data = parse_blte(enc_raw)
        enc = parse_encoding_file(enc_data)
        # dict ckey -> ekey
        self.encoding = enc

    def read_ekey(self, ekey):
        ents = self.idx.get(ekey[:9])
        if not ents:
            raise KeyError("ekey not in local idx: %s" % ekey.hex())
        for data_file, offset, size, _eks in ents:
            path = os.path.join(DATA_DIR, "data", "data.%03d" % data_file)
            with open(path, "rb") as f:
                f.seek(offset + 0x1E)  # local-storage entries carry a 30-byte header
                df = f.read(size)
            try:
                _, content = parse_blte(df)
            except Exception:
                continue
            # verify full key matches
            import hashlib
            if hashlib.md5(content).digest() == ekey:
                return df
        # fallback: return first candidate
        return df

    def read_ckey(self, ckey):
        ckey = hexkey_to_bytes(ckey) if isinstance(ckey, str) else ckey
        ekey = self.encoding[int.from_bytes(ckey, "big")]
        ekey = ekey.to_bytes((ekey.bit_length() + 7) // 8, "big").rjust(9, b"\x00")
        return self.read_ekey(ekey)

    def read_blob_by_ekey9(self, ekey9):
        _, content = parse_blte(self.read_ekey(ekey9))
        return content

    def load_tree(self):
        # vfs-root = <CKey> <EKey>; the EKey blob is the TVFS root directory
        vfs_root_ekey = hexkey_to_bytes(self.cfg["vfs-root"].split()[1])
        root_blob = self.read_blob_by_ekey9(vfs_root_ekey[:9])
        return parse_tvfs(root_blob, read_blob=self.read_blob_by_ekey9)

    def read_tree_file(self, ekey9):
        _, content = parse_blte(self.read_ekey(ekey9))
        return content


def main():
    casc = CASC()
    paths = casc.load_tree()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    if cmd == "list":
        filt = (sys.argv[2] if len(sys.argv) > 2 else "").upper()
        n = 0
        for p in sorted(paths):
            if filt in p.upper():
                print(p)
                n += 1
        print("total: %d (filtered %d)" % (len(paths), n), file=sys.stderr)
    elif cmd == "extract":
        filt = (sys.argv[sys.argv.index("--filter") + 1] if "--filter" in sys.argv else "").upper()
        out = sys.argv[sys.argv.index("--out") + 1]
        for p, ek in sorted(paths.items()):
            if filt and filt not in p.upper():
                continue
            dest = os.path.join(out, p.replace("\\", "/"))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            try:
                content = casc.read_tree_file(ek)
            except Exception as e:
                print("FAIL %s: %s" % (p, e), file=sys.stderr)
                continue
            with open(dest, "wb") as f:
                f.write(content)
            print("ok", p, len(content), file=sys.stderr)
    else:
        raise SystemExit("unknown command")


# ---------------------------------------------------------------------------
# TVFS (TACT VFS) root parsing
# ---------------------------------------------------------------------------

def be(data, off, n):
    return int.from_bytes(data[off:off + n], "big")


def parse_tvfs(data, prefix="", out=None, depth=0, read_blob=None):
    """Parse one TVFS directory file. Returns out: dict path -> 9-byte ekey.

    read_blob(ekey9) -> decoded bytes, used to recurse into sub-directory
    TVFS files (may be None on first level call from load_tree).
    """
    assert data[:4] == b"TVFS", "not a TVFS file"
    if out is None:
        out = {}
    _header_size = data[5]
    path_off = be(data, 0x0C, 4)
    path_size = be(data, 0x10, 4)
    vfs_off = be(data, 0x14, 4)
    _vfs_size = be(data, 0x18, 4)
    cft_off = be(data, 0x1C, 4)
    cft_size = be(data, 0x20, 4)
    if cft_size > 0xFFFFFF:
        cft_offs_size = 4
    elif cft_size > 0xFFFF:
        cft_offs_size = 3
    elif cft_size > 0xFF:
        cft_offs_size = 2
    else:
        cft_offs_size = 1

    FOLDER = 0x80000000

    def walk(ptr, end, pfx):
        while ptr < end:
            pre_sep = False
            if data[ptr] == 0:
                pre_sep = True
                ptr += 1
            name = b""
            if ptr < end and data[ptr] != 0xFF:
                n = data[ptr]
                ptr += 1
                name = data[ptr:ptr + n]
                ptr += n
            post_sep = False
            if ptr < end and data[ptr] == 0:
                post_sep = True
                ptr += 1
            node_value = None
            if ptr < end and data[ptr] == 0xFF:
                node_value = be(data, ptr + 1, 4)
                ptr += 5
            elif ptr < end:
                post_sep = True
            path = pfx + ("\\" if pre_sep else "") + name.decode("utf-8", "replace") + ("\\" if post_sep else "")
            if node_value is None:
                continue
            if node_value & FOLDER:
                sub_len = node_value & 0x7FFFFFFF
                sub_end = ptr + sub_len - 4
                walk(ptr, sub_end, path)
                ptr = sub_end
            else:
                vp = vfs_off + node_value
                span_count = data[vp]
                vp += 1
                if span_count == 1:
                    _span_off = be(data, vp, 4)
                    _span_size = be(data, vp + 4, 4)
                    cft_pos = be(data, vp + 8, cft_offs_size)
                    ekey = data[cft_off + cft_pos: cft_off + cft_pos + 9]
                    blob = None
                    if read_blob is not None:
                        try:
                            blob = read_blob(ekey)
                        except Exception:
                            blob = None
                    if blob is not None and blob[:4] == b"TVFS":
                        # container file (e.g. war3.w3mod): its sub-TVFS holds
                        # the directory contents, relative to the container
                        sub_pfx = path if path.endswith("\\") else path + "\\"
                        parse_tvfs(blob, sub_pfx, out, depth + 1, read_blob)
                    else:
                        out[path] = ekey
                # multi-span and unsupported spans ignored

    walk(path_off, path_off + path_size, prefix)
    return out


if __name__ == "__main__":
    main()
