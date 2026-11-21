"""Оригінали голосів юнітів із ВЛАСНОЇ копії гри → структура, з якою працює студія.

  make refs                                   # EN з CASC гри → reference-en/units/…
  RU_PACK=<…>/ruru.w3mod make refs            # + RU з мовного пакета репаку → reference/units/…

EN: `casc_read.py extract` у `reference-en-raw/` (файли переміщуються).
RU: у CASC гри російської озвучки немає (лише ~5 %); її містить російський мовний пакет
репаку (`Localizations/Russian/ruru.w3mod`, теку `units/`) — файли КОПІЮЮТЬСЯ, пакет не змінюється.
Розкладання — за списком `data/inventory-units.csv` (раса/юніт/файл). casc_read «склеює» теки з префіксом
імені (`heheadhunteryes1.wav` = headhunter/headhunteryes1.wav), тому зіставляємо в межах
раси: точний збіг імені, інакше найкоротше ім'я, що закінчується на потрібне, де «прилиплий»
префікс — початок назви теки юніта (`find`). Файли переміщуються. Ідемпотентно.
Аудіо гри не комітиться (.gitignore).
"""
from __future__ import annotations

import argparse
import csv
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GAME_ROOT = Path(os.environ.get("WC3_GAME_ROOT", "/Applications/Warcraft III Classic"))
RU_PACK_DEFAULT = GAME_ROOT / "Localizations/Russian/ruru.w3mod"


def find(name: str, unit: str, index: dict[str, Path]) -> Path | None:
    if name in index:
        return index[name]
    cands = [k for k in index if k.endswith(name) and unit.startswith(k[:len(k) - len(name)])]
    return index[min(cands, key=len)] if cands else None


def layout(raw_units: Path, out_units: Path, targets: list[str], copy: bool = False) -> tuple[int, int]:
    """targets: ['orc/peon/peonyes1.wav', …] → out_units/<target>. Повертає (є, без пари).
    copy=False переміщує (тимчасові витяги), copy=True копіює (чужі джерела не змінюються)."""
    by_race: dict[str, list[str]] = {}
    for t in targets:
        by_race.setdefault(t.split("/")[0], []).append(t)
    done = missing = 0
    for race, items in sorted(by_race.items()):
        rdir = raw_units / race
        index = {p.name.lower(): p for p in rdir.rglob("*.wav")} if rdir.is_dir() else {}
        for t in sorted(items):
            dst = out_units / t
            if dst.exists():
                done += 1
                continue
            parts = t.split("/")
            src = find(parts[-1].lower(), parts[-2].lower(), index)
            if src is None:
                missing += 1
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            if copy:
                shutil.copy2(src, dst)
            else:
                os.replace(src, dst)
            index.pop(src.name.lower())
            done += 1
    return done, missing


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--no-extract", action="store_true", help="EN: лише розкласти вже витягнуте")
    ap.add_argument("--ru-pack", type=Path, default=Path(os.environ.get("RU_PACK") or RU_PACK_DEFAULT),
                    help="тека ruru.w3mod російського мовного пакета")
    a = ap.parse_args()
    with open(ROOT / "data/inventory-units.csv", encoding="utf-8") as f:
        targets = [r["file"].lower() for r in csv.DictReader(f)]

    raw = ROOT / "reference-en-raw"
    if not a.no_extract:
        subprocess.run([sys.executable, str(ROOT / "tools/casc_read.py"), "extract", "--filter",
                        "war3.w3mod\\_locales\\enus.w3mod\\units\\", "--out", str(raw)],
                       check=True, stdout=subprocess.DEVNULL)
    done, missing = layout(raw / "war3.w3mod/_locales/enus.w3mod/units", ROOT / "reference-en/units", targets)
    print(f"EN: {done} файлів у reference-en/units, без пари: {missing}")

    if (a.ru_pack / "units").is_dir():
        done, missing = layout(a.ru_pack / "units", ROOT / "reference/units", targets, copy=True)
        print(f"RU: {done} файлів у reference/units, без пари: {missing}")
    elif not (ROOT / "reference/units").is_dir():
        print(f"RU: пакет не знайдено ({a.ru_pack}). Студія працюватиме з англійським оригіналом;\n"
              "    для російського вкажіть RU_PACK=<…>/Localizations/Russian/ruru.w3mod", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
