"""Текстова українізація: завантаження upstream (warcraft-in-ua) у gitignored кеш + НАШІ перетворення. Лише stdlib.

Юридично (docs/decisions/0006-*): upstream без ліцензії, тож жодного його файлу в git немає. Тут лише код:
  * resolve_head / fetch: останній коміт гілки main (або --ref), кеш `data/local/cache/textpack/<sha>/<variant>/`;
    LIGHT = tree API + raw-файли (звірка git blob sha1 з відповіддю API), FULL = zip коміту (sha256 архіву).
    У manifest.json кешу: commit, sha256 архіву (для LIGHT — digest списку файлів), sha256 кожного файлу.
  * add_hotkey_markers: Classic 1.31 показує гарячі клавіші лише розміткою в Tip; Reforged-переклад її не має.
  * build_fdf131: FDF формату 1.31 = структура (id, порядок, CRLF/BOM) з власних файлів гри + значення upstream.
  * build: готове дерево встановлення для цілі (data/targets/*.json) у `data/local/cache/build/<ціль>/`.
Помилка розкладу upstream (немає Units/*.txt тощо) → TextPackError ДО будь-якого запису в гру.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))   # `python -I` не додає теку скрипта
import fdf_strings  # noqa: E402

ROOT = Path(os.environ.get("WC3UA_ROOT") or Path(__file__).resolve().parent.parent)
REPO = "warcraft-in-ua/WarCraft3-Reforged-Ukrainian"
BRANCH = "main"
API = "https://api.github.com"
RAW = "https://raw.githubusercontent.com"
ZIP = "https://codeload.github.com/{repo}/zip/{sha}"
UA = "wc3-ua-textpack"                                   # без персональних даних і токенів
VARIANT_RE = {"light": re.compile(r"^(LIGHT[^/]*)/_retail_/"), "full": re.compile(r"^(FULL[^/]*)/_retail_/")}
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
MARK = "|cffffcc00"


class TextPackError(Exception):
    pass


def cache_root() -> Path:
    return Path(os.environ.get("WC3UA_ROOT") or ROOT) / "data/local/cache"


# ------------------------------------------------------------------ мережа (у тестах підміняється)
def http_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def http_download(url: str, dest: Path) -> tuple[str, int]:
    """Потоково в dest; повертає (sha256, розмір)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    h, n = hashlib.sha256(), 0
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
            h.update(chunk)
            n += len(chunk)
    return h.hexdigest(), n


def git_blob_sha1(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()  # noqa: S324 (формат git, не криптозахист)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


# ------------------------------------------------------------------ upstream: HEAD, кеш
def resolve_commit(ref: str | None = None) -> str:
    """Повний sha: --ref (sha/тег/гілка) або поточний HEAD гілки main. Без токенів."""
    if ref and SHA_RE.match(ref):
        return ref
    d = http_json(f"{API}/repos/{REPO}/commits/{urllib.parse.quote(ref or BRANCH, safe='')}")
    sha = d.get("sha", "") if isinstance(d, dict) else ""
    if not SHA_RE.match(sha):
        raise TextPackError(f"GitHub не повернув коміт для {ref or BRANCH}")
    return sha


def dirs_for(target: dict, full: bool) -> set[str]:
    """Верхні теки upstream `_retail_/`, потрібні цілі."""
    d = {"Units", "UI", "doodads"}
    if target.get("fonts") == "upstream":
        d.add("fonts")
    if full:
        d |= set(target.get("full_dirs", []))
    return d


def _variant_root(paths, variant: str) -> str:
    rx = VARIANT_RE[variant]
    for p in paths:
        m = rx.match(p)
        if m:
            return m.group(0)
    raise TextPackError(f"розклад upstream змінився: немає теки {variant.upper()}*/_retail_/ — оновіть tools/textpack.py")


def _cache_ok(base: Path, man: dict, dirs: set[str]) -> bool:
    if not dirs <= set(man.get("dirs", [])):
        return False
    return all((base / "files" / r).is_file() and (base / "files" / r).stat().st_size == i["size"] for r, i in man["files"].items())


def fetch(commit: str, variant: str, dirs: set[str], log=print) -> Path:
    """Гарантує кеш коміту; повертає теку `files/` (шляхи як у `_retail_/`). Той самий коміт → без завантаження."""
    base = cache_root() / "textpack" / commit / variant
    mp = base / "manifest.json"
    old = json.loads(mp.read_text(encoding="utf-8")) if mp.is_file() else {}
    if old and _cache_ok(base, old, dirs):
        log(f"кеш: {commit[:10]} ({variant}) вже є — завантаження не потрібне")
        return base / "files"
    dirs = dirs | set(old.get("dirs", []))
    tree = http_json(f"{API}/repos/{REPO}/git/trees/{commit}?recursive=1")
    if not isinstance(tree, dict) or tree.get("truncated") or not tree.get("tree"):
        raise TextPackError("GitHub tree API: порожня або обрізана відповідь — не ризикую встановлювати частину")
    blobs = {i["path"]: i for i in tree["tree"] if i.get("type") == "blob"}
    prefix = _variant_root(blobs, variant)
    want = {p[len(prefix):]: i for p, i in blobs.items() if p.startswith(prefix) and p[len(prefix):].split("/")[0] in dirs}
    if not any(r.startswith("Units/") and r.lower().endswith(".txt") for r in want):
        raise TextPackError("розклад upstream змінився: у _retail_/Units немає *.txt")
    stage = base.with_name(base.name + ".part")
    shutil.rmtree(stage, ignore_errors=True)
    files, archive = {}, ""
    if variant == "light":
        for rel, it in sorted(want.items()):
            h, n = http_download(f"{RAW}/{REPO}/{commit}/{urllib.parse.quote(prefix + rel)}", stage / "files" / rel)
            if git_blob_sha1(stage / "files" / rel) != it.get("sha"):
                shutil.rmtree(stage, ignore_errors=True)
                raise TextPackError(f"{rel}: git sha1 не збігається з API — файл пошкоджено або підмінено")
            files[rel] = {"sha256": h, "size": n}
        archive = hashlib.sha256("\n".join(f"{r}\t{i['sha256']}" for r, i in sorted(files.items())).encode()).hexdigest()
    else:
        zp = stage / "archive.zip"
        archive, _ = http_download(ZIP.format(repo=REPO, sha=commit), zp)
        with zipfile.ZipFile(zp) as z:
            for info in z.infolist():
                name = info.filename.split("/", 1)[1] if "/" in info.filename else ""
                if info.is_dir() or not name.startswith(prefix):
                    continue
                rel = name[len(prefix):]
                if rel.startswith(("/", "..")) or ".." in rel.split("/") or rel.split("/")[0] not in dirs:
                    continue
                out = stage / "files" / rel
                out.parent.mkdir(parents=True, exist_ok=True)
                with z.open(info) as src, open(out, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                files[rel] = {"sha256": sha256_file(out), "size": out.stat().st_size}
        zp.unlink()
        if not any(r.startswith("Units/") for r in files):
            shutil.rmtree(stage, ignore_errors=True)
            raise TextPackError("розклад upstream змінився: в архіві немає _retail_/Units")
    manifest = {"repo": REPO, "commit": commit, "variant": variant, "archive_sha256": archive, "dirs": sorted(dirs),
                "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "files": files}
    (stage / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    shutil.rmtree(base, ignore_errors=True)
    base.parent.mkdir(parents=True, exist_ok=True)
    os.replace(stage, base)
    log(f"завантажено {len(files)} файлів, коміт {commit[:10]} ({variant})")
    return base / "files"


def get_upstream(target: dict, full: bool, ref: str | None = None, log=print) -> dict:
    """{commit, variant, archive_sha256, files_dir}. HEAD зрушив → нове завантаження; офлайн → останній кеш."""
    variant = "full" if full else "light"
    head_file = cache_root() / "textpack" / f"HEAD-{variant}.json"
    try:
        commit = resolve_commit(ref)
        if not ref:
            head_file.parent.mkdir(parents=True, exist_ok=True)
            head_file.write_text(json.dumps({"commit": commit}), encoding="utf-8")
    except (OSError, ValueError, TextPackError) as ex:
        if ref or not head_file.is_file():
            raise TextPackError(f"не вдалося визначити версію upstream: {ex}") from ex
        commit = json.loads(head_file.read_text(encoding="utf-8"))["commit"]
        log(f"УВАГА: GitHub недоступний ({ex}); використовую останній кеш {commit[:10]}")
    files_dir = fetch(commit, variant, dirs_for(target, full), log)
    man = json.loads((files_dir.parent / "manifest.json").read_text(encoding="utf-8"))
    return {"commit": commit, "variant": variant, "archive_sha256": man["archive_sha256"], "files_dir": files_dir}


# ------------------------------------------------------------------ перетворення 1: гарячі клавіші
SECTION_RE = re.compile(r"^\[([^\]]+)\]")
KEY_RE = re.compile(r"^([A-Za-z]+)=(.*?)(\r?\n?)$", re.S)
PAIRS = {"tip": "hotkey", "researchtip": "researchhotkey", "untip": "unhotkey", "awakentip": "hotkey", "revivetip": "hotkey"}


def split_values(v: str) -> list[str]:
    """Значення Warcraft: рівні через кому; елемент у лапках може містити коми. Збірка назад — ','.join."""
    out, i, n = [], 0, len(v)
    while i <= n:
        if i < n and v[i] == '"':
            j = v.find('"', i + 1)
            while j != -1 and j + 1 < n and v[j + 1] != ",":
                j = v.find('"', j + 1)
            j = n - 1 if j == -1 else j
            out.append(v[i:j + 1])
            i = j + 2
        else:
            j = v.find(",", i)
            j = n if j == -1 else j
            out.append(v[i:j])
            i = j + 1
    return out


def _unq(s: str) -> str:
    s = s.strip()
    return s[1:-1] if len(s) >= 2 and s[0] == s[-1] == '"' else s


def marker_piece(piece: str, key: str) -> str | None:
    """Додає ` (|cffffcc00K|r)` в кінець елемента (у лапках — перед закриваючою). None = лишити як є."""
    body = _unq(piece)
    if not body.strip() or "|cffc3dbff" in body.lower() or f"{MARK}{key}|r".lower() in body.lower():
        return None
    add = f" ({MARK}{key}|r)"
    if len(piece) >= 2 and piece[0] == piece[-1] == '"':
        return piece[:-1] + add + '"'
    return piece + add


def _keys_of(v: str) -> list[str]:
    return [_unq(p) for p in split_values(v.strip())]


def add_hotkey_markers(text: str) -> tuple[str, dict]:
    """(новий текст, статистика). BOM, CRLF/LF, порядок рядків і значення Hotkey не змінюються.
    Елемент, що вже підсвічує свою клавішу (|cffffcc00K|r), і підказки |cffc3dbff пропускаємо; розмітку рівнів
    `[|cffffcc00рівень 1|r]` пропуском НЕ вважаємо (інакше всі героїчні здібності лишились би без клавіші)."""
    bom = text.startswith("﻿")
    lines = text.lstrip("﻿").splitlines(keepends=True)
    st = {"sections_with_hotkey": 0, "sections_without_markup": 0, "sections_changed": 0, "tips_changed": 0,
          "markers_added": 0, "skipped_already": 0, "skipped_badkey": 0}
    secs: list[dict[str, int]] = []
    cur: dict[str, int] | None = None
    for i, ln in enumerate(lines):
        if SECTION_RE.match(ln):
            cur = {}
            secs.append(cur)
        elif cur is not None and not ln.lstrip().startswith("//"):
            m = KEY_RE.match(ln)
            if m:
                cur.setdefault(m.group(1).lower(), i)
    for sec in secs:
        def hk(k, sec=sec):
            return KEY_RE.match(lines[sec[k]]).group(2) if k in sec else None
        if hk("hotkey") is not None:
            st["sections_with_hotkey"] += 1
            tip = hk("tip")
            st["sections_without_markup"] += bool(tip is not None and "|c" not in tip.lower())
        changed = False
        for tk, hkk in PAIRS.items():
            if tk not in sec or hkk not in sec:
                continue
            tm, keys = KEY_RE.match(lines[sec[tk]]), _keys_of(KEY_RE.match(lines[sec[hkk]]).group(2))
            pieces, new, did = split_values(tm.group(2).rstrip()), [], 0
            for n, p in enumerate(pieces):
                k = keys[n] if n < len(keys) else keys[-1]
                if len(k) != 1 or not k.isalnum():
                    st["skipped_badkey"] += 1
                    new.append(p)
                    continue
                r = marker_piece(p, k.upper())
                if r is None:
                    st["skipped_already"] += 1
                    new.append(p)
                else:
                    new.append(r)
                    did += 1
            if did:
                tail = tm.group(2)[len(tm.group(2).rstrip()):]
                lines[sec[tk]] = f"{lines[sec[tk]][:lines[sec[tk]].index('=') + 1]}{','.join(new)}{tail}{tm.group(3)}"
                st["tips_changed"] += 1
                st["markers_added"] += did
                changed = True
        st["sections_changed"] += changed
    return ("﻿" if bom else "") + "".join(lines), st


def merge_stats(a: dict, b: dict) -> dict:
    return {k: a.get(k, 0) + b.get(k, 0) for k in set(a) | set(b)}


# ------------------------------------------------------------------ перетворення 2: FDF формату 1.31
_FMT = re.compile(r"%(?:\d+\$)?[-+ #0]*\d*(?:\.\d+)?[sdifxXc%]")


def _spec(v: str) -> list[str]:
    return sorted(_FMT.findall(v))


def build_fdf131(upstream: Path, template: Path, out: Path, overrides: dict[str, str] | None = None) -> dict:
    """Структура з template (власний FDF гри: ті самі id, порядок, CRLF/BOM, що перевірений рос. пакет 1.31) +
    значення upstream за id. id без пари або з іншими %-специфікаторами → лишається значення template (звіт)."""
    up = {e["id"]: e["value"] for e in fdf_strings.extract(upstream)["entries"]}
    tpl = {e["id"]: e["value"] for e in fdf_strings.extract(template)["entries"]}
    if not tpl:
        raise TextPackError(f"шаблон {template.name}: немає рядків-значень — формат FDF інший?")
    mapping, missing, mismatch = dict(overrides or {}), [], []
    for ident, tv in tpl.items():
        if ident in mapping:
            continue
        if ident not in up:
            missing.append(ident)
        elif _spec(up[ident]) != _spec(tv):
            mismatch.append(ident)
        else:
            mapping[ident] = up[ident]
    out.parent.mkdir(parents=True, exist_ok=True)
    fdf_strings.patch(template, mapping, out)
    return {"ids": len(tpl), "translated": len(set(mapping) & set(tpl)), "missing_in_upstream": missing, "format_mismatch": mismatch}


def load_overrides() -> dict[str, str]:
    """Власні формулювання (data/text-overrides/fdf131.json, наша робота) мають перевагу над upstream."""
    p = Path(__file__).resolve().parent.parent / "data/text-overrides/fdf131.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


# ------------------------------------------------------------------ цілі
def targets_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "data/targets"


def load_target(tid: str) -> dict:
    p = targets_dir() / f"{tid}.json"
    if not p.is_file():
        known = ", ".join(sorted(x.stem for x in targets_dir().glob("*.json")))
        raise TextPackError(f"невідома ціль {tid!r}; є: {known}")
    return json.loads(p.read_text(encoding="utf-8"))


def all_targets() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(targets_dir().glob("*.json"))]


# ------------------------------------------------------------------ джерела власних файлів гри (шаблон FDF, шрифти)
def casc_extract(game: Path, filt: str, out: Path) -> list[Path]:
    """Файли з CASC самої гри користувача (tools/casc_read.py, потрібен PyCASC: make setup-refs)."""
    v = ROOT / (".venv/Scripts/python.exe" if sys.platform.startswith("win") else ".venv/bin/python")
    py = [str(v), "-I"] if v.exists() else [sys.executable, "-I"]
    env = dict(os.environ, WC3_GAME_ROOT=str(game), PYTHONUTF8="1")
    r = subprocess.run([*py, str(Path(__file__).resolve().parent / "casc_read.py"), "extract", "--filter", filt, "--out", str(out)],
                       capture_output=True, text=True, env=env)
    if r.returncode:
        raise TextPackError(f"CASC гри недоступний ({(r.stderr or r.stdout).strip().splitlines()[-1:]}); потрібен `make setup-refs`")
    return sorted(p for p in out.rglob("*") if p.is_file())


def own_source(game: Path, kind: str, explicit: Path | None, work: Path) -> Path | None:
    """Тека з власними файлами гри: kind 'fdf' (enUS framedef, 1.31) або 'fonts' (рос. мовний пакет).
    Порядок: явний шлях → мовний пакет у <гра>/Localizations → CASC гри."""
    if explicit:
        return Path(explicit)
    if kind == "fonts":
        cands = [game / "Localizations/Russian/ruru.w3mod/fonts"]
        cf = "_locales\\ruru.w3mod\\fonts\\"
        sub = "war3.w3mod/_locales/ruru.w3mod/fonts"
    else:
        cands = []
        cf = "_locales\\enus.w3mod\\ui\\framedef\\"
        sub = "war3.w3mod/_locales/enus.w3mod/ui/framedef"
    for c in cands:
        if c.is_dir():
            return c
    d = work / f"own-{kind}"
    if not (d / sub).is_dir():
        casc_extract(game, cf, d)
    return d / sub if (d / sub).is_dir() else None


# ------------------------------------------------------------------ збірка дерева встановлення
@dataclass
class BuildResult:
    files: dict[str, Path] = field(default_factory=dict)       # rel (відносно кореня цілі) → файл-джерело
    stats: dict = field(default_factory=dict)
    skipped: list[str] = field(default_factory=list)            # що не зроблено і чому (розклад upstream змінився тощо)
    source: dict = field(default_factory=dict)                  # commit, variant, archive_sha256


def _excluded(rel: str, target: dict) -> bool:
    return any(re.search(p, rel, re.I) for p in target.get("exclude", []))


def build(target: dict, up: dict, game: Path | None = None, fdf_template: Path | None = None,
          fonts_from: Path | None = None, out: Path | None = None) -> BuildResult:
    """up = get_upstream(...). Усе у відрізі `out` (типово data/local/cache/build/<ціль>/); у гру нічого не пишемо."""
    res = BuildResult(source={k: up[k] for k in ("commit", "variant", "archive_sha256")})
    src = Path(up["files_dir"])
    out = Path(out or cache_root() / "build" / target["id"])
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    allf = sorted(p.relative_to(src).as_posix() for p in src.rglob("*") if p.is_file())
    txt = [r for r in allf if re.fullmatch(r"Units/[^/]+\.txt", r)]
    if not txt:
        raise TextPackError("розклад upstream змінився: Units/*.txt не знайдено")
    st: dict = {}
    for rel in allf:
        top = rel.split("/")[0]
        if _excluded(rel, target) or rel.startswith("UI/framedef/"):
            continue
        if top == "fonts" and target.get("fonts") != "upstream":
            continue
        if top not in ("Units", "UI", "doodads", "fonts", *target.get("full_dirs", [])):
            res.skipped.append(f"{rel}: невідома тека upstream (розклад змінився?)")
            continue
        f = src / rel
        if target.get("hotkey_markers") and rel.lower().endswith(".txt") and top == "Units":
            new, s = add_hotkey_markers(f.read_text(encoding="utf-8"))
            st = merge_stats(st, s)
            dst = out / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(new.encode("utf-8"))
            res.files[rel] = dst
        else:
            res.files[rel] = f
    res.stats["hotkeys"] = st
    mode = target.get("fdf", "none")
    fdfs = sorted(r for r in allf if r.startswith("UI/framedef/") and r.endswith(".fdf"))
    if mode == "upstream":
        res.files.update({r: src / r for r in fdfs})
    elif mode in ("131", "template-only"):
        tdir = fdf_template
        if tdir is None and game is not None and mode == "131":
            try:
                tdir = own_source(game, "fdf", None, cache_root() / "own")
            except TextPackError as ex:
                res.skipped.append(f"FDF 1.31: {ex}")
        if tdir is None or not Path(tdir).is_dir():
            res.skipped.append("FDF 1.31: немає шаблону (власні FDF гри). Вкажіть --fdf-template або виконайте `make setup-refs`; "
                               "меню лишиться англійським, але НЕ зламається")
        else:
            rep = {}
            for r in fdfs:
                name = Path(r).name
                tpl = next((p for p in Path(tdir).iterdir() if p.name.lower() == name.lower()), None)
                if tpl is None:
                    res.skipped.append(f"{r}: у шаблоні немає такого файлу — пропущено")
                    continue
                dst = out / r
                rep[name] = build_fdf131(src / r, tpl, dst, load_overrides())
                res.files[r] = dst
            got = {Path(r).name for r in res.files if r.startswith("UI/framedef/")}
            for need in ("globalstrings.fdf",):
                if need not in got:
                    res.skipped.append(f"{need}: не збудовано — меню 1.31 не буде українським")
            res.stats["fdf"] = rep
    fm = target.get("fonts")
    if fm == "own":
        fdir = None
        if game is not None or fonts_from is not None:
            try:
                fdir = own_source(game, "fonts", fonts_from, cache_root() / "own") if game else Path(fonts_from)
            except TextPackError as ex:
                res.skipped.append(f"шрифти: {ex}")
        got = []
        for name in target.get("font_files", []):
            p = next((q for q in Path(fdir).iterdir() if q.name.lower() == name), None) if fdir and Path(fdir).is_dir() else None
            if p:
                res.files[f"fonts/{name}"] = p
                got.append(name)
        if not got:
            res.skipped.append("шрифти: мовний пакет (рос.) не знайдено — кирилиця може не відображатись (--fonts-from <тека>)")
        res.stats["fonts"] = got
    res.stats["files"] = len(res.files)
    return res
