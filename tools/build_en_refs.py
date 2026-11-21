"""Розкладає англійські оригінали голосів у ту ж структуру, що й російські референси.

Вхід:  reference-en-raw/ (результат `casc_read.py extract` для war3.w3mod\\_locales\\enus.w3mod\\units\\)
Вихід: reference-en/units/<race>/<unit>/<file>.wav — для кожного файлу з reference/units/.

casc_read «склеює» теки з префіксом імені (`heheadhunteryes1.wav` = headhunter/headhunteryes1.wav),
тому зіставляємо за ім'ям у межах раси: точний збіг, інакше найкоротше ім'я, що закінчується
на потрібне, де «прилиплий» префікс — початок назви теки юніта. Файли переміщуються. Ідемпотентно.
Запуск:
  .venv/bin/python tools/casc_read.py extract --filter "war3.w3mod\\_locales\\enus.w3mod\\units\\" --out reference-en-raw
  .venv/bin/python -I tools/build_en_refs.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "reference-en-raw/war3.w3mod/_locales/enus.w3mod/units"
RU = ROOT / "reference/units"
EN = ROOT / "reference-en/units"


def find(name: str, unit: str, index: dict[str, Path]) -> Path | None:
    if name in index:
        return index[name]
    cands = [k for k in index if k.endswith(name) and unit.startswith(k[:len(k) - len(name)])]
    return index[min(cands, key=len)] if cands else None


def main() -> int:
    if not RU.is_dir():
        print("немає reference/units — спершу рос. референси", file=sys.stderr)
        return 1
    done = missing = 0
    for race_dir in sorted(p for p in RU.iterdir() if p.is_dir()):
        index = {p.name.lower(): p for p in (RAW / race_dir.name).rglob("*.wav")} if (RAW / race_dir.name).is_dir() else {}
        for ref in sorted(race_dir.rglob("*.wav")):
            dst = EN / ref.relative_to(RU)
            if dst.exists():
                done += 1
                continue
            src = find(ref.name.lower(), ref.parent.name.lower(), index)
            if src is None:
                missing += 1
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            os.replace(src, dst)
            index.pop(src.name.lower())
            done += 1
    print(f"англійських оригіналів: {done}, без пари: {missing}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
