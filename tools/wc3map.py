#!/usr/bin/env python3
"""Minimal MPQ v1 reader/writer for Warcraft III melee maps.

Reads:  extract files by name from a .w3m/.w3x map (handles compressed,
encrypted (listfile), pkware/zlib decompression).
Writes: rebuilds a map archive with the same file set, keeping the original
0x200-byte W3X header untouched. New files are stored uncompressed and
unencrypted (WC3 accepts this).

w3i helpers: parse/patch the map info file (name, author, description,
suggested players), following TRIGSTR references into war3map.wts.
"""
import struct
import zlib

# ---------------------------------------------------------------------------
# MPQ crypt table (standard)
# ---------------------------------------------------------------------------

def _make_crypt_table():
    table = [0] * 0x500
    seed = 0x00100001
    for i in range(0x100):
        idx = i
        for _ in range(5):
            seed = (seed * 125 + 3) % 0x2AAAAB
            t1 = (seed & 0xFFFF) << 0x10
            seed = (seed * 125 + 3) % 0x2AAAAB
            t2 = (seed & 0xFFFF)
            table[idx] = (t1 | t2)
            idx += 0x100
    return table

CRYPT_TABLE = _make_crypt_table()

MPQ_HASH_TABLE_INDEX = 0
MPQ_HASH_NAME_A = 1
MPQ_HASH_NAME_B = 2
MPQ_HASH_FILE_KEY = 3


def mpq_hash(name, hash_type):
    seed1, seed2 = 0x7FED7FED, 0xEEEEEEEE
    for ch in name.upper().encode("ascii", "replace"):
        ch = 0x20 if ch == 0x2F else ch  # '/' -> '\'
        seed1 = (CRYPT_TABLE[(hash_type << 8) + ch] ^ (seed1 + seed2)) & 0xFFFFFFFF
        seed2 = (ch + seed1 + seed2 + (seed2 << 5) + 3) & 0xFFFFFFFF
    return seed1


def _crypt_words(data, key, decrypt_dir):
    """MPQ block crypt (StormLib-compatible). seed1 starts at the key.

    Both directions share the same keystream except that the seed2 update
    uses the plaintext word in encrypt mode and the decrypted word in
    decrypt mode.
    """
    n = len(data) // 4
    seed1, seed2 = key, 0xEEEEEEEE
    out = bytearray(len(data))
    for i in range(n):
        v = struct.unpack_from("<I", data, i * 4)[0]
        seed2 = (seed2 + CRYPT_TABLE[0x400 + (seed1 & 0xFF)]) & 0xFFFFFFFF
        ch = (v ^ ((seed1 + seed2) & 0xFFFFFFFF)) & 0xFFFFFFFF
        struct.pack_into("<I", out, i * 4, ch)
        seed1 = (((~seed1) << 0x15) + 0x11111111 | (seed1 >> 0x0B)) & 0xFFFFFFFF
        fb = (v if not decrypt_dir else ch)
        seed2 = (fb + seed2 + (seed2 << 5) + 3) & 0xFFFFFFFF
    return bytes(out)


def decrypt(data, key):
    return _crypt_words(data, key, True)


def encrypt(data, key):
    return _crypt_words(data, key, False)


# ---------------------------------------------------------------------------
# Reader
# ---------------------------------------------------------------------------

FLAG_EXISTS = 0x80000000
FLAG_SINGLE_UNIT = 0x01000000
FLAG_ENCRYPTED = 0x00010000
FLAG_FIX_KEY = 0x00020000
FLAG_COMPRESSED = 0x00000200


class MapArchive:
    def __init__(self, path):
        self.path = path
        self.raw = open(path, "rb").read()
        data = self.raw
        pos = data.find(b"MPQ\x1a")
        if pos < 0:
            raise ValueError("no MPQ header")
        (hdr_size, arc_size, fmt_ver, block_size, hash_pos, block_pos,
         hash_size, block_size_n) = struct.unpack_from("<IIHHIIII", data, pos + 4)
        self.mpq_header_off = pos
        self.sector_size = 512 << block_size
        self.hash_pos = pos + hash_pos
        self.block_pos = pos + block_pos
        self.hash_table = self._read_table(self.hash_pos, hash_size,
                                           mpq_hash("(hash table)", MPQ_HASH_FILE_KEY))
        self.block_table = self._read_table(self.block_pos, block_size_n,
                                            mpq_hash("(block table)", MPQ_HASH_FILE_KEY))
        self.entries = {}  # normalized name -> block index
        for _i, h in enumerate(self.hash_table):
            if h[0] == 0xFFFFFFFF and h[1] == 0xFFFFFFFF and h[3] == 0xFFFFFFFF:
                continue
            bi = h[3]
            if bi >= len(self.block_table):
                continue
            self.entries.setdefault((h[0], h[1]), bi)

    def _read_table(self, off, count, key):
        raw = decrypt(self.raw[off:off + count * 16], key)
        return [struct.unpack_from("<IIII", raw, i * 16) for i in range(count)]

    def list_files(self):
        names = []
        try:
            lf = self.read_file("(listfile)")
            names = [n for n in lf.decode("utf-8", "replace").split("\r\n") if n]
        except Exception:
            pass
        return names

    def read_file(self, name):
        h1, h2 = mpq_hash(name, MPQ_HASH_NAME_A), mpq_hash(name, MPQ_HASH_NAME_B)
        bi = self.entries.get((h1, h2))
        if bi is None:
            raise KeyError(name)
        return self.read_block(bi, name)

    def read_block(self, bi, name=""):
        off, csize, fsize, flags = self.block_table[bi]
        start = self.mpq_header_off + off
        data = self.raw[start:start + csize]
        key = 0
        if flags & FLAG_ENCRYPTED:
            key = mpq_hash(name.split("\\")[-1], MPQ_HASH_FILE_KEY)
            if flags & FLAG_FIX_KEY:
                key = (key + bi - (self.mpq_header_off)) & 0xFFFFFFFF
        if not (flags & FLAG_EXISTS):
            raise ValueError("block not exists: %s" % name)
        if flags & FLAG_ENCRYPTED:
            if flags & FLAG_SINGLE_UNIT:
                data = decrypt(data, key)
            else:
                # sector table is encrypted too
                nsect = (fsize + self.sector_size - 1) // self.sector_size
                sect_tbl = decrypt(data[: (nsect + 1) * 4], key)
                offs = struct.unpack("<%dI" % (nsect + 1), sect_tbl)
                out = bytearray()
                for s in range(nsect):
                    chunk = data[offs[s]:offs[s + 1]]
                    if flags & FLAG_COMPRESSED and len(chunk) > 0:
                        if len(chunk) < self.sector_size:
                            chunk = _decompress_chunk(chunk)
                    out += chunk
                data = bytes(out)
                return data
        if flags & FLAG_SINGLE_UNIT:
            if flags & FLAG_COMPRESSED:
                if data[:1] == b"\x00":
                    data = data[1:]
                else:
                    data = _pkdecompress(data) or zlib.decompress(data, -15)
            return data
        # multi-sector, not encrypted
        nsect = (fsize + self.sector_size - 1) // self.sector_size
        offs = struct.unpack("<%dI" % (nsect + 1), data[: (nsect + 1) * 4])
        out = bytearray()
        for s in range(nsect):
            chunk = data[offs[s]:offs[s + 1]]
            if flags & FLAG_COMPRESSED and len(chunk) > 0:
                if len(chunk) < self.sector_size:
                    chunk = _decompress_chunk(chunk)
            out += chunk
        return bytes(out)


def _pkdecompress(data):
    """Pkware DCL explode; returns None if unsupported."""
    return None  # WC3 melee maps do not use pkware in practice


def _decompress_chunk(chunk):
    """Decompress one MPQ sector (first byte is the compression mask)."""
    mask = chunk[0]
    if mask & 0x02:  # zlib
        d = zlib.decompressobj(15)
        out = d.decompress(chunk[1:])
        out += d.flush()
        return out
    if mask & 0x08:  # pkware
        out = _pkdecompress(chunk[1:])
        if out is None:
            raise ValueError("pkware compression unsupported")
        return out
    if mask == 0x00:
        return chunk[1:]
    raise ValueError("unsupported compression mask 0x%02x" % mask)


# ---------------------------------------------------------------------------
# Writer: rebuild map archive, all files stored uncompressed
# ---------------------------------------------------------------------------

def build_map(header_0x200, files, listfile_names=None):
    """files: list of (name, data bytes). Returns full map file bytes with the
    original 0x200-byte W3X header preserved and a fresh MPQ v1 archive."""
    if listfile_names is None:
        listfile_names = [n for n, _ in files]
    names = list(listfile_names) + ["(listfile)"]
    blobs = [d for _, d in files] + ["\r\n".join(names).encode("utf-8")]

    sector_bits = 3  # 512 << 3 = 4096
    hash_count = len(names) * 2
    # round hash count up to a reasonable power-of-two-ish size
    hash_count = max(16, 1 << (hash_count - 1).bit_length())

    header_size = 0x20
    mpq_off = len(header_0x200)  # 0x200
    hash_off = mpq_off + header_size
    block_off = hash_off + hash_count * 16
    data_off = block_off + len(names) * 16

    blocks = []
    cur = data_off - mpq_off
    packed = bytearray()
    for blob in blobs:
        packed += blob
        blocks.append((cur, len(blob), len(blob), FLAG_EXISTS))
        cur += len(blob)

    # hash table
    _hashtable = [b"\xff" * 16] * hash_count  # filled below
    ht = [(0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF)] * hash_count
    _free = 0
    for i, name in enumerate(names):
        idx = mpq_hash(name, MPQ_HASH_TABLE_INDEX) & (hash_count - 1)
        while ht[idx][3] != 0xFFFFFFFF:
            idx = (idx + 1) % hash_count
        ht[idx] = (mpq_hash(name, MPQ_HASH_NAME_A),
                   mpq_hash(name, MPQ_HASH_NAME_B),
                   0,  # locale/platform
                   i)
    ht_raw = b"".join(struct.pack("<IIII", *e) for e in ht)
    ht_raw = encrypt(ht_raw, mpq_hash("(hash table)", MPQ_HASH_FILE_KEY))
    bt_raw = b"".join(struct.pack("<IIII", *e) for e in blocks)
    bt_raw = encrypt(bt_raw, mpq_hash("(block table)", MPQ_HASH_FILE_KEY))

    arc_size = block_off + len(bt_raw) - mpq_off
    header = struct.pack("<IIHHIIII",
                         0x20,          # header size
                         arc_size,      # archive size (relative to MPQ header)
                         0,             # format version 0 (classic)
                         sector_bits,
                         0x20,          # hash table pos (relative to MPQ header)
                         0x20 + hash_count * 16,
                         hash_count,
                         len(names))
    out = bytearray(header_0x200)
    out += header
    out += ht_raw
    out += bt_raw
    out += packed
    assert len(out) == data_off + len(packed)
    return bytes(out)


# ---------------------------------------------------------------------------
# war3map.w3i parsing / patching
# ---------------------------------------------------------------------------

def read_cstr(buf, pos):
    end = buf.index(b"\x00", pos)
    return buf[pos:end].decode("utf-8", "replace"), end + 1


def write_cstr(s):
    return s.encode("utf-8") + b"\x00"


def parse_w3i(data):
    pos = 0
    version, saves, editor = struct.unpack_from("<III", data, pos)
    pos += 12
    if version >= 27:
        # 1.31+/Reforged format: four extra u32 before the string block
        pos += 16
    name, pos = read_cstr(data, pos)
    author, pos = read_cstr(data, pos)
    desc, pos = read_cstr(data, pos)
    players, pos = read_cstr(data, pos)
    return {
        "version": version, "saves": saves, "editor": editor,
        "name": name, "author": author, "description": desc,
        "players": players, "rest_offset": pos,
    }


def patch_w3i(data, name=None, author=None, description=None, players=None):
    """Rewrite the four leading strings; everything after is copied verbatim."""
    meta = parse_w3i(data)
    out = bytearray()
    out += struct.pack("<III", meta["version"], meta["saves"], meta["editor"])
    out += write_cstr(name if name is not None else meta["name"])
    out += write_cstr(author if author is not None else meta["author"])
    out += write_cstr(description if description is not None else meta["description"])
    out += write_cstr(players if players is not None else meta["players"])
    out += data[meta["rest_offset"]:]
    return bytes(out)


def resolve_trigstr(value, wts):
    """If value is a TRIGSTR_xxx reference, look it up in parsed wts strings."""
    if value.upper().startswith("TRIGSTR_"):
        try:
            key = int(value[8:])
        except ValueError:
            return value
        return wts.get(key, value)
    return value


def parse_wts(data):
    """Parse war3map.wts into {id: text}."""
    import re
    out = {}
    for m in re.finditer(rb"STRING (\d+)\s*\r?\n\{\r?\n(.*?)\r?\n\}", data, re.S):
        out[int(m.group(1))] = m.group(2).decode("utf-8", "replace")
    return out


def rebuild_map(src_path, overrides=None):
    """Rebuild a map archive.

    overrides: dict {name-or-block-index: bytes-or-None}; None = drop file.
    Unchanged files are copied verbatim (raw sector data, original flags),
    so no decompression of untouched files is needed. Overridden files are
    stored uncompressed as single units. Unknown-name files keep their
    original hash-table identity (name hashes).
    Returns (bytes, kept) where kept is [(hash_entry, data)].
    """
    m = MapArchive(src_path)
    overrides = overrides or {}

    by_block = {}
    for h in m.hash_table:
        if h[0] == 0xFFFFFFFF and h[1] == 0xFFFFFFFF and h[3] == 0xFFFFFFFF:
            continue
        by_block.setdefault(h[3], []).append(h)

    name_of_block = {}
    for name in overrides:
        if isinstance(name, str):
            h1, h2 = mpq_hash(name, MPQ_HASH_NAME_A), mpq_hash(name, MPQ_HASH_NAME_B)
            bi = m.entries.get((h1, h2))
            if bi is not None:
                name_of_block[bi] = name

    kept = []  # (hash_entry, raw_data, block_entry_or_None)
    for bi in sorted(by_block):
        name = name_of_block.get(bi)
        ov = overrides.get(bi, overrides.get(name, "__missing__"))
        if ov is None:
            continue
        off, csize, fsize, flags = m.block_table[bi]
        if ov == "__missing__":
            raw = m.raw[m.mpq_header_off + off: m.mpq_header_off + off + csize]
            kept.append((by_block[bi][0], raw, (off, csize, fsize, flags)))
        else:
            kept.append((by_block[bi][0], ov, None))
        for h in by_block[bi][1:]:
            kept.append((h, kept[-1][1], kept[-1][2]))

    hash_count = max(16, 1 << (2 * len(kept) - 1).bit_length())
    ht = [(0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF)] * hash_count
    for n, (h, _data, _be) in enumerate(kept):
        idx = h[0] & (hash_count - 1)
        while ht[idx][3] != 0xFFFFFFFF:
            idx = (idx + 1) % hash_count
        ht[idx] = (h[0], h[1], 0, n)

    header_size = 0x20
    block_off = header_size + hash_count * 16
    data_off = block_off + len(kept) * 16

    blocks = []
    packed = bytearray()
    cur = data_off
    for _h, data, be in kept:
        if be is None:
            blocks.append((cur, len(data), len(data), FLAG_EXISTS | FLAG_SINGLE_UNIT))
        else:
            _, csize, fsize, flags = be
            blocks.append((cur, csize, fsize, flags))
        packed += data
        cur += len(data)

    ht_raw = encrypt(b"".join(struct.pack("<IIII", *e) for e in ht),
                     mpq_hash("(hash table)", MPQ_HASH_FILE_KEY))
    bt_raw = encrypt(b"".join(struct.pack("<IIII", *e) for e in blocks),
                     mpq_hash("(block table)", MPQ_HASH_FILE_KEY))

    header = b"MPQ\x1a" + struct.pack("<IIHHIIII",
                         0x20, data_off + len(packed), 0, 3,
                         header_size, block_off, hash_count, len(kept))
    out = bytearray(b"\x00" * m.mpq_header_off)
    out += header + ht_raw + bt_raw + packed
    return bytes(out), kept
