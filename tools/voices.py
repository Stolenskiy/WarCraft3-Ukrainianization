"""Голоси спільноти: публікація власних записів, вибір «чий голос» і декодування для гри.

Пакет автора (у git): живі записи — CC BY 4.0; ШІ-репліки (`"ai": true`) — ліцензія двигуна (Fish: CC BY-NC 4.0), див. voices/LICENSE.md:
  voices/<автор>/voice.json     {id, name, license, consent, created, updated}
  voices/<автор>/manifest.json  {<шлях у грі>: {sha256, dur, peak_db[, ai, license, engine]}}   напр. "Units/orc/peon/peonyes1.wav"
  voices/<автор>/units/<раса>/<юніт>/<файл>.flac   FLAC 22050 Hz mono s16 — ГОТОВІ для гри файли

Публікуємо лише game-files/ (власні затверджені дублі користувача) — ніколи reference*/ чи аудіо гри.
Локальний вибір (gitignored) — data/studio/voice-choice.json:
  {"default": [автор…], "race": {"orc": автор}, "unit": {"orc/peon": автор}, "line": {"Units/orc/peon/x.wav": автор}}
Спеціальний автор "local" — власна тека game-files/ (ще не опублікована). Пріоритет: line > unit > race > default.
Перший, у кого Є файл, виграє; якщо обраний автор файлу не має — наступний за default, позначка fallback.

  make publish-voice AUTHOR=<нік> CONSENT=1     (git із коду не викликається — лише підказка команд)
"""
from __future__ import annotations

import argparse
import array
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import wave
from dataclasses import dataclass, field
from pathlib import Path

SR = 22050
LICENSE = "CC BY 4.0"                 # живі записи
AI_LICENSE = "CC BY-NC 4.0"          # ШІ-репліки за замовчуванням (Fish Audio Research License — некомерційна, ADR 0007)
DEFAULT_ENGINE = "fish-s2-pro"
AUTHOR_RE = re.compile(r"^[a-z0-9-]{2,32}$")
MIN_DUR, MAX_DUR, MAX_BYTES = 0.2, 30.0, 1_000_000
LOCAL = "local"
CHOICE_REL = "data/studio/voice-choice.json"
SETTINGS_REL = "data/studio/settings-local.json"
CACHE_REL = "data/studio/voice-cache"
CONSENT_TEXT = "Це мій власний голос; дозволяю використання за ліцензією CC BY 4.0"


class VoiceError(Exception):
    """Помилка, яку варто показати користувачеві."""


# ---------------------------------------------------------------- шляхи й формат
def rel_to_flac(rel: str) -> str:
    """Units/orc/peon/x.wav → units/orc/peon/x.flac (відносно voices/<автор>/)."""
    parts = rel.split("/")
    if len(parts) != 4 or parts[0] != "Units" or not rel.endswith(".wav"):
        raise VoiceError(f"не шлях юніта Units/<раса>/<юніт>/<файл>.wav: {rel}")
    return "units/" + "/".join(parts[1:])[:-4] + ".flac"


def flac_to_rel(flac_rel: str) -> str:
    parts = flac_rel.split("/")
    if len(parts) != 4 or parts[0] != "units" or not flac_rel.endswith(".flac"):
        raise VoiceError(f"не шлях units/<раса>/<юніт>/<файл>.flac: {flac_rel}")
    return "Units/" + "/".join(parts[1:])[:-5] + ".wav"


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def check_author(a: str) -> str:
    if not isinstance(a, str) or not AUTHOR_RE.fullmatch(a):
        raise VoiceError("нікнейм: 2–32 символи a-z, 0-9, «-»")
    return a


def wav_info(path: Path) -> tuple[float, float]:
    """(тривалість, пік у dBFS) wav s16 — stdlib."""
    import math
    with wave.open(str(path), "rb") as w:
        if w.getsampwidth() != 2:
            raise VoiceError(f"очікується 16-бітний WAV: {path.name}")
        n, fr = w.getnframes(), w.getframerate()
        data = array.array("h")
        data.frombytes(w.readframes(n))
    if sys.byteorder == "big":
        data.byteswap()
    peak = max((max(data), -min(data)), default=0)
    return round(n / fr, 3), (round(20 * math.log10(peak / 32768), 2) if peak else -120.0)


def flac_info(path: Path) -> dict:
    """Метадані FLAC без ffmpeg: {rate, channels, bits, dur, tags} з STREAMINFO; tags — кількість коментарів/обкладинок
    (мають бути 0: метадані автора у файлах не потрібні). Некоректний файл → VoiceError."""
    with open(path, "rb") as f:
        if f.read(4) != b"fLaC":
            raise VoiceError("не FLAC")
        info, tags, first = None, 0, True
        while True:
            h = f.read(4)
            if len(h) < 4:
                raise VoiceError("обірваний заголовок FLAC")
            last, btype, size = h[0] >> 7, h[0] & 0x7F, int.from_bytes(h[1:], "big")
            body = f.read(size)
            if first and btype != 0:
                raise VoiceError("немає STREAMINFO")
            first = False
            if btype == 0:
                if len(body) < 34:
                    raise VoiceError("STREAMINFO обірваний")
                v = int.from_bytes(body[10:18], "big")
                info = {"rate": v >> 44, "channels": ((v >> 41) & 7) + 1, "bits": ((v >> 36) & 31) + 1,
                        "samples": v & ((1 << 36) - 1)}
            elif btype == 4:                       # VORBIS_COMMENT: vendor + лічильник коментарів
                vl = int.from_bytes(body[:4], "little")
                tags += int.from_bytes(body[4 + vl:8 + vl], "little") if len(body) >= 8 + vl else 1
            elif btype == 6:                       # PICTURE
                tags += 1
            if last:
                break
    info["dur"] = round(info["samples"] / info["rate"], 3) if info["rate"] else 0.0
    info["tags"] = tags
    return info


def _ffmpeg(*args: str) -> None:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], capture_output=True, timeout=60)
    if r.returncode:
        raise VoiceError("ffmpeg: " + r.stderr.decode(errors="replace").strip()[-300:])


def encode_flac(wav: Path, flac: Path) -> None:
    """wav → FLAC 22050/mono/s16 без метаданих; детермінований (повторна публікація не змінює байтів)."""
    _ffmpeg("-i", str(wav), "-map_metadata", "-1", "-fflags", "+bitexact", "-flags:a", "+bitexact",
            "-ar", str(SR), "-ac", "1", "-sample_fmt", "s16", "-compression_level", "8", str(flac))


def stage(flac: Path, root: Path) -> Path:
    """FLAC → wav у кеші data/studio/voice-cache/<sha>.wav (для копіювання в гру й прослуховування)."""
    out = root / CACHE_REL / f"{sha256(flac)}.wav"
    if not out.is_file():
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(".tmp.wav")
        try:
            _ffmpeg("-i", str(flac), "-ar", str(SR), "-ac", "1", "-sample_fmt", "s16", "-f", "wav", str(tmp))
            os.replace(tmp, out)
        finally:
            tmp.unlink(missing_ok=True)
    return out


# ---------------------------------------------------------------- пакети авторів
def voices_dir(root: Path) -> Path:
    return root / "voices"


def _read_json(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def authors(root: Path) -> list[str]:
    """Автори з валідним voice.json (id збігається з текою)."""
    d = voices_dir(root)
    out = []
    for p in sorted(d.iterdir()) if d.is_dir() else []:
        vj = _read_json(p / "voice.json", None)
        if p.is_dir() and AUTHOR_RE.fullmatch(p.name) and isinstance(vj, dict) and vj.get("id") == p.name:
            out.append(p.name)
    return out


def manifest(root: Path, author: str) -> dict:
    m = _read_json(voices_dir(root) / author / "manifest.json", {})
    return m if isinstance(m, dict) else {}


def canon_rel(rel: str) -> str:
    """Шлях у грі в канонічному вигляді: «Units/» + решта в нижньому регістрі (так у грі й у data/inventory-units.csv).
    game-files/ може мати «Units/Orc/…» — на macOS це той самий файл, але пакет і маніфест мусять бути однакові в усіх."""
    return rel[:6] + rel[6:].lower() if rel[:6].lower() == "units/" else rel


def local_rels(root: Path) -> list[str]:
    g = root / "game-files"
    return sorted(p.relative_to(g).as_posix() for p in g.rglob("*.wav")) if g.is_dir() else []


def originals(root: Path) -> dict:
    """game-files/.originals.json {rel: {lang, sha256}} — оригінали Blizzard, які користувач залишив; їх не публікуємо."""
    m = _read_json(Path(root) / "game-files/.originals.json", {})
    return m if isinstance(m, dict) else {}


def engine_license(engine: str | None) -> str:
    """Ліцензія ШІ-реплік двигуна (метадані двигуна в tools/aistudio/engines); невідомий двигун → CC BY-NC 4.0."""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from aistudio.engines import output_license
        return output_license(engine)
    except Exception:      # noqa: BLE001 — без реєстру діє найсуворіша ліцензія
        return AI_LICENSE


def ai_rels(root: Path) -> set[str]:
    """Шляхи, чий обраний дубль має source == "ai" (згенеровано ШІ власним голосом)."""
    return set(ai_engines(root))


def ai_engines(root: Path) -> dict[str, str]:
    """{шлях: двигун} для обраних дублів із source == "ai": стан студії data/studio/units-*.json."""
    out: dict[str, str] = {}
    for sp in sorted((Path(root) / "data/studio").glob("units-*.json")):
        st = _read_json(sp, {})
        for gid, lines in (st.get("groups") or {}).items() if isinstance(st, dict) else []:
            for lid, e in (lines or {}).items():
                if not isinstance(e, dict) or not e.get("approved"):
                    continue
                for t in e.get("takes", []):
                    if isinstance(t, dict) and t.get("file") == e["approved"] and t.get("source") == "ai":
                        out[f"Units/{sp.stem[6:]}/{gid}/{lid}"] = str(t.get("engine") or DEFAULT_ENGINE)
    return out


def wav_pcm(path: Path) -> bytes:
    with wave.open(str(path), "rb") as w:
        return w.readframes(w.getnframes())


def author_path(root: Path, author: str, rel: str) -> Path | None:
    """Файл автора для rel (wav для local, flac для інших) — лише якщо rel є в маніфесті й sha збігається."""
    if author == LOCAL:
        p = root / "game-files" / rel
        return p if rel in set(local_rels(root)) and p.is_file() else None
    if author not in authors(root):
        return None
    ent = manifest(root, author).get(rel)
    if not isinstance(ent, dict):
        return None
    try:
        p = voices_dir(root) / author / rel_to_flac(rel)
    except VoiceError:
        return None
    return p if p.is_file() and sha256(p) == ent.get("sha256") else None


def author_rels(root: Path, author: str) -> list[str]:
    return local_rels(root) if author == LOCAL else sorted(manifest(root, author))


def coverage(rels) -> dict:
    """{раса: {юніт: кількість}} за шляхами Units/<раса>/<юніт>/…"""
    out: dict[str, dict[str, int]] = {}
    for r in rels:
        p = r.split("/")
        if len(p) == 4 and p[0] == "Units":
            u = out.setdefault(p[1].lower(), {})
            u[p[2].lower()] = u.get(p[2].lower(), 0) + 1
    return out


def author_info(root: Path, author: str) -> dict:
    rels = author_rels(root, author)
    if author == LOCAL:
        return {"id": LOCAL, "name": "Мій голос (локально)", "local": True, "license": "", "files": len(rels),
                "bytes": 0, "ai": len(ai_rels(root) & set(rels)), "ai_license": AI_LICENSE, "coverage": coverage(rels)}
    vj = _read_json(voices_dir(root) / author / "voice.json", {})
    size = sum(p.stat().st_size for p in (voices_dir(root) / author).rglob("*.flac"))
    return {"id": author, "name": vj.get("name", author), "local": False, "license": vj.get("license", ""),
            "created": vj.get("created"), "updated": vj.get("updated"), "files": len(rels), "bytes": size,
            "ai": sum(1 for e in manifest(root, author).values() if isinstance(e, dict) and e.get("ai")),
            "ai_license": vj.get("ai_license"), "coverage": coverage(rels)}


# ---------------------------------------------------------------- публікація
def publish(author: str, nickname: str, root: Path, consent: bool = False) -> dict:
    """game-files/**.wav → voices/<author>/ (FLAC + manifest.json + voice.json); прибирає FLAC без затвердженого wav."""
    if consent is not True:
        raise VoiceError("потрібна згода: «" + CONSENT_TEXT + "»")
    check_author(author)
    nickname = nickname if isinstance(nickname, str) else ""
    if "@" in nickname or not 1 <= len(nickname.strip()) <= 40 or nickname != nickname.strip():
        raise VoiceError("ім'я автора: 1–40 символів, без «@» (не вказуйте пошту чи справжнє ім'я)")
    root = Path(root)
    out = voices_dir(root) / author
    old = manifest(root, author)
    man: dict[str, dict] = {}
    added = updated = unchanged = 0
    skipped: list[dict] = []
    own, ai = {canon_rel(r) for r in originals(root)}, {canon_rel(r): eng for r, eng in ai_engines(root).items()}
    for src_rel in local_rels(root):
        src = root / "game-files" / src_rel
        rel = canon_rel(src_rel)
        if rel in own:
            skipped.append({"rel": rel, "reason": "оригінал гри (залишено) — не публікується"})
            continue
        try:
            frel = rel_to_flac(rel)
        except VoiceError as ex:
            skipped.append({"rel": rel, "reason": str(ex)})
            continue
        dur, peak = wav_info(src)
        if not MIN_DUR <= dur <= MAX_DUR:
            skipped.append({"rel": rel, "reason": f"тривалість {dur} с поза {MIN_DUR}–{MAX_DUR}"})
            continue
        dst = out / frel
        dst.parent.mkdir(parents=True, exist_ok=True)
        tmp = dst.with_name(dst.name + ".tmp.flac")
        try:
            encode_flac(src, tmp)
            if tmp.stat().st_size > MAX_BYTES:
                skipped.append({"rel": rel, "reason": "файл більший за 1 МБ"})
                continue
            digest = sha256(tmp)
            if dst.is_file() and sha256(dst) == digest and rel in old:
                unchanged += 1
            else:
                updated, added = (updated + 1, added) if dst.is_file() else (updated, added + 1)
                os.replace(tmp, dst)
        finally:
            tmp.unlink(missing_ok=True)
        man[rel] = {"sha256": digest, "dur": dur, "peak_db": peak,
                    **({"ai": True, "license": engine_license(ai[rel]), "engine": ai[rel]} if rel in ai else {})}
    if not man:
        raise VoiceError("немає що публікувати: game-files/ порожня або всі файли пропущено")
    removed = 0
    for p in sorted((out / "units").rglob("*.flac")) if (out / "units").is_dir() else []:
        rel = flac_to_rel(p.relative_to(out).as_posix())
        if rel not in man:
            p.unlink()
            removed += 1
    for d in sorted((out / "units").rglob("*"), reverse=True) if (out / "units").is_dir() else []:
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()
    today = dt.date.today().isoformat()
    ai_lics = {e["license"] for e in man.values() if e.get("ai")}
    ai_license = (sorted(ai_lics)[0] if len(ai_lics) == 1 else AI_LICENSE) if ai_lics else None   # змішані → найсуворіша
    vj = _read_json(out / "voice.json", {})
    (out / "manifest.json").write_text(json.dumps(man, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    (out / "voice.json").write_text(json.dumps({
        "id": author, "name": nickname, "license": LICENSE, "consent": True,
        **({"ai_license": ai_license} if ai_license else {}),
        "created": vj.get("created", today), "updated": today}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    total = sum(p.stat().st_size for p in out.rglob("*.flac"))
    return {"author": author, "added": added, "updated": updated, "removed": removed, "unchanged": unchanged,
            "files": len(man), "skipped": skipped, "total_mb": round(total / 1e6, 2), "git": git_commands(author)}


def git_commands(author: str) -> list[str]:
    """Підказка (код git не запускає): гілка → коміт → пуш → PR."""
    return [f"git switch -c voices/{author}", f"git add voices/{author}",
            f'git commit -m "voices: {author}"', f"git push -u origin voices/{author}",
            f'gh pr create --title "voices: {author}" --body "Голос {author}, ліцензія {LICENSE}"']


# ---------------------------------------------------------------- локальний вибір
def _empty_choice() -> dict:
    return {"default": [LOCAL], "race": {}, "unit": {}, "line": {}}


def load_choice(root: Path) -> dict:
    raw = _read_json(Path(root) / CHOICE_REL, {})
    c = _empty_choice()
    if isinstance(raw, dict):
        if isinstance(raw.get("default"), list):
            c["default"] = [a for a in raw["default"] if isinstance(a, str)]
        for k in ("race", "unit", "line"):
            if isinstance(raw.get(k), dict):
                c[k] = {a: b for a, b in raw[k].items() if isinstance(a, str) and isinstance(b, str)}
    return c


UNIT_KEY_RE = re.compile(r"[a-z0-9_]+/[a-z0-9_]+")
LINE_KEY_RE = re.compile(r"Units/[a-z0-9_]+/[a-z0-9_]+/[A-Za-z0-9_.-]+\.wav")


def save_choice(root: Path, patch: dict) -> dict:
    """Замінює переданні розділи (default/race/unit/line); None або "" як значення — прибрати перевизначення."""
    if not isinstance(patch, dict):
        raise VoiceError("очікується об'єкт")
    root = Path(root)
    known = {LOCAL, *authors(root)}
    c = load_choice(root)
    if "default" in patch:
        d = patch["default"]
        if not isinstance(d, list) or not all(isinstance(a, str) for a in d) or len(set(d)) != len(d):
            raise VoiceError("default має бути списком унікальних авторів")
        c["default"] = d
    for key, ok in (("race", lambda k: re.fullmatch(r"[a-z0-9_]+", k)), ("unit", lambda k: UNIT_KEY_RE.fullmatch(k)),
                    ("line", lambda k: LINE_KEY_RE.fullmatch(k))):
        if key in patch:
            m = patch[key]
            if not isinstance(m, dict):
                raise VoiceError(f"{key} має бути об'єктом")
            for k, v in m.items():
                if not isinstance(k, str) or not ok(k):
                    raise VoiceError(f"некоректний ключ {key}: {k!r}")
                if v not in (None, "") and not isinstance(v, str):
                    raise VoiceError(f"некоректний автор для {k}")
            c[key] = {k: v for k, v in m.items() if v}
    for a in [*c["default"], *c["race"].values(), *c["unit"].values(), *c["line"].values()]:
        if a not in known:
            raise VoiceError(f"невідомий автор: {a}")
    p = root / CHOICE_REL
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(c, indent=1, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, p)
    return c


def get_nickname(root: Path) -> str:
    n = _read_json(Path(root) / SETTINGS_REL, {}).get("author")
    return n if isinstance(n, str) else ""


def set_nickname(root: Path, nick: str) -> str:
    nick = check_author(nick)
    p = Path(root) / SETTINGS_REL
    p.parent.mkdir(parents=True, exist_ok=True)
    cur = _read_json(p, {})
    cur = cur if isinstance(cur, dict) else {}
    cur["author"] = nick
    p.write_text(json.dumps(cur, indent=1), encoding="utf-8")
    return nick


# ---------------------------------------------------------------- розв'язання вибору
@dataclass
class Pick:
    rel: str
    author: str                 # звідки реально береться файл
    path: Path                  # wav (local) або flac
    wanted: str = ""            # кого обрано явно (line/unit/race); "" — лише порядок за замовчуванням
    fallback: bool = False      # обраний автор файлу не має
    alts: list[str] = field(default_factory=list)   # усі, хто має цей файл


def wanted_author(choice: dict, rel: str) -> str:
    p = rel.split("/")
    unit = f"{p[1].lower()}/{p[2].lower()}" if len(p) >= 3 else ""
    return choice["line"].get(rel) or choice["unit"].get(unit) or choice["race"].get(p[1].lower() if len(p) > 1 else "") or ""


def resolve(root: Path, choice: dict | None = None) -> dict[str, Pick]:
    """rel → Pick для всіх файлів, які має хоч один «активний» автор (default + згадані в перевизначеннях)."""
    root = Path(root)
    choice = choice or load_choice(root)
    active = list(dict.fromkeys([*choice["default"], *choice["race"].values(), *choice["unit"].values(),
                                 *choice["line"].values()]))
    have: dict[str, dict[str, Path]] = {}
    for a in active:
        for rel in author_rels(root, a):
            p = author_path(root, a, rel)
            if p:
                have.setdefault(rel, {})[a] = p
    out: dict[str, Pick] = {}
    for rel, by in sorted(have.items()):
        want = wanted_author(choice, rel)
        order = ([want] if want else []) + [a for a in choice["default"] if a != want] \
            + [a for a in active if a not in choice["default"] and a != want]
        win = next(a for a in order if a in by)
        out[rel] = Pick(rel, win, by[win], want, bool(want) and win != want, list(by))
    return out


def build_sources(root: Path, choice: dict | None = None) -> dict[str, Path]:
    return {rel: p.path for rel, p in resolve(root, choice).items()}


# ---------------------------------------------------------------- CLI
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Голоси спільноти")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("publish", help="game-files/ → voices/<автор>/")
    p.add_argument("--author", required=True)
    p.add_argument("--name")
    p.add_argument("--consent", action="store_true", help=CONSENT_TEXT)
    a = ap.parse_args(argv)
    root = Path(os.environ.get("WC3UA_ROOT") or Path(__file__).resolve().parent.parent)
    try:
        r = publish(a.author, a.name or a.author, root, consent=a.consent)
    except VoiceError as ex:
        print(f"Помилка: {ex}" + ("" if a.consent else "\nДодайте CONSENT=1 (make) / --consent, якщо це ваш голос."))
        return 1
    print(f"Опубліковано: +{r['added']} нових, {r['updated']} оновлено, {r['removed']} прибрано, "
          f"{r['unchanged']} без змін; усього {r['files']} файлів, {r['total_mb']} МБ")
    for s in r["skipped"]:
        print(f"  пропущено {s['rel']}: {s['reason']}")
    print("\nДалі (виконайте самі):\n  " + "\n  ".join(r["git"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
