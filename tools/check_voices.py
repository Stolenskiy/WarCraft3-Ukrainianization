"""Перевірка пакетів голосів у voices/ (запускається в `make check`, тобто в CI на кожному PR).

Для кожного voices/<автор>/:
  * voice.json: id = назва теки (a-z0-9-, 2–32), license = CC BY 4.0, consent = true, name без «@»; ніде немає «@»;
  * лише voice.json, manifest.json і units/<раса>/<юніт>/<файл>.flac (інше — «сторонній файл»);
  * кожен FLAC: 22050 Hz, mono, 16 біт, ≤ 1 МБ, 0.2–30 с, без метаданих, є в manifest.json зі збіжним sha256;
  * шлях відповідає відомій репліці з data/inventory-units.csv; у маніфесті немає зайвих записів.
  .venv/bin/python -I tools/check_voices.py
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
import tempfile
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))   # `python -I` не додає теку скрипта
import voices  # noqa: E402


def known_lines(root: Path) -> set[str] | None:
    p = root / "data/inventory-units.csv"
    if not p.is_file():
        return None
    with open(p, encoding="utf-8", newline="") as f:
        return {"units/" + r["file"].lower() for r in csv.DictReader(f)}


def check(root: Path) -> list[str]:
    root = Path(root)
    base = root / "voices"
    errs: list[str] = []
    if not base.exists():
        return errs
    known = known_lines(root)
    if known is None:
        errs.append("data/inventory-units.csv відсутній — не можна звірити репліки")
        known = set()
    for top in sorted(base.iterdir()):
        if top.is_dir():
            errs += _author(root, top, known)
        else:
            errs.append(f"voices/{top.name}: сторонній файл (очікуються лише теки авторів)")
    return errs


def _author(root: Path, top: Path, known: set[str]) -> list[str]:
    a, e = top.name, []
    pre = f"voices/{a}"
    if not voices.AUTHOR_RE.fullmatch(a):
        e.append(f"{pre}: некоректний нікнейм (a-z0-9-, 2–32)")
    if a.startswith("reference") or "audio" in a:
        e.append(f"{pre}: заборонена назва теки")
    vj = _json(top / "voice.json", e, pre)
    if isinstance(vj, dict):
        if vj.get("id") != a:
            e.append(f"{pre}/voice.json: id має дорівнювати назві теки")
        if vj.get("license") != voices.LICENSE:
            e.append(f"{pre}/voice.json: license має бути {voices.LICENSE}")
        if vj.get("consent") is not True:
            e.append(f"{pre}/voice.json: consent має бути true")
        if not isinstance(vj.get("name"), str) or not 1 <= len(vj["name"]) <= 40:
            e.append(f"{pre}/voice.json: name — рядок 1–40 символів")
    elif vj is not None:
        e.append(f"{pre}/voice.json: очікується об'єкт")
    for fn in ("voice.json", "manifest.json"):
        p = top / fn
        if p.is_file() and "@" in p.read_text(encoding="utf-8", errors="replace"):
            e.append(f"{pre}/{fn}: містить «@» (пошта/контакти не публікуємо)")
    man = _json(top / "manifest.json", e, pre)
    man = man if isinstance(man, dict) else {}
    seen = set()
    for p in sorted(top.rglob("*")):
        if p.is_dir():
            continue
        rel = p.relative_to(top).as_posix()
        if rel in ("voice.json", "manifest.json"):
            continue
        if not rel.startswith("units/") or not rel.endswith(".flac"):
            e.append(f"{pre}/{rel}: сторонній файл")
            continue
        e += _flac(top, p, rel, man, known, pre)
        e += _original(root, p, rel, pre)
        seen.add(rel)
    for grel in man:
        try:
            if voices.rel_to_flac(grel) not in seen:
                e.append(f"{pre}/manifest.json: {grel} немає у units/")
        except voices.VoiceError:
            e.append(f"{pre}/manifest.json: некоректний ключ {grel!r}")
    return e


def _original(root: Path, p: Path, rel: str, pre: str) -> list[str]:
    """Заборона публікувати оригінал Blizzard: збіг PCM з файлом із game-files/.originals.json (якщо він є локально)."""
    try:
        grel = voices.flac_to_rel(rel)
    except voices.VoiceError:
        return []
    ent, local = voices.originals(root).get(grel), root / "game-files" / grel
    if ent is None or not local.is_file():
        return []
    try:
        with tempfile.TemporaryDirectory() as d:
            wav = Path(d) / "x.wav"
            voices._ffmpeg("-i", str(p), "-f", "wav", str(wav))
            same = voices.wav_pcm(wav) == voices.wav_pcm(local)
    except (voices.VoiceError, OSError, EOFError, wave.Error):
        return []
    return [f"{pre}/{rel}: збігається з оригіналом гри (.originals.json) — публікувати не можна"] if same else []


def _json(p: Path, e: list[str], pre: str):
    if not p.is_file():
        e.append(f"{pre}/{p.name}: немає файла")
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except ValueError as ex:
        e.append(f"{pre}/{p.name}: некоректний JSON ({ex})")
        return None


def _flac(top: Path, p: Path, rel: str, man: dict, known: set[str], pre: str) -> list[str]:
    e, who = [], f"{pre}/{rel}"
    try:
        grel = voices.flac_to_rel(rel)
    except voices.VoiceError as ex:
        return [f"{who}: {ex}"]
    if grel.lower() not in known or grel[6:] != grel[6:].lower():
        e.append(f"{who}: невідома репліка {grel} (немає в data/inventory-units.csv)")
    size = p.stat().st_size
    if size > voices.MAX_BYTES:
        e.append(f"{who}: {size} байт > {voices.MAX_BYTES}")
    try:
        i = voices.flac_info(p)
    except voices.VoiceError as ex:
        return e + [f"{who}: {ex}"]
    if (i["rate"], i["channels"], i["bits"]) != (voices.SR, 1, 16):
        e.append(f"{who}: формат {i['rate']} Hz/{i['channels']} кан./{i['bits']} біт, потрібно {voices.SR}/1/16")
    if not voices.MIN_DUR <= i["dur"] <= voices.MAX_DUR:
        e.append(f"{who}: тривалість {i['dur']} с поза {voices.MIN_DUR}–{voices.MAX_DUR}")
    if i["tags"]:
        e.append(f"{who}: у файлі є метадані (теги/обкладинка)")
    ent = man.get(grel)
    if not isinstance(ent, dict):
        e.append(f"{who}: немає в manifest.json")
    else:
        if ent.get("sha256") != voices.sha256(p):
            e.append(f"{who}: sha256 не збігається з manifest.json")
        if not isinstance(ent.get("dur"), (int, float)) or abs(ent["dur"] - i["dur"]) > 0.05:
            e.append(f"{who}: dur у manifest.json не збігається з файлом")
        if not isinstance(ent.get("peak_db"), (int, float)):
            e.append(f"{who}: peak_db у manifest.json має бути числом")
        if "ai" in ent and ent["ai"] is not True:
            e.append(f"{who}: ai у manifest.json має бути true або відсутнім")
        if not re.fullmatch(r"[0-9a-f]{64}", str(ent.get("sha256"))):
            e.append(f"{who}: некоректний sha256 у manifest.json")
    return e


def main(argv: list[str] | None = None) -> int:
    root = Path(os.environ.get("WC3UA_ROOT") or Path(__file__).resolve().parent.parent)
    errs = check(root)
    for x in errs:
        print("✗", x)
    n = sum(1 for _ in (root / "voices").rglob("*.flac")) if (root / "voices").is_dir() else 0
    print(f"voices: {'ПОМИЛКИ — ' + str(len(errs)) if errs else 'ok'} ({n} FLAC)")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
