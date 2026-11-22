"""Спільні дрібниці ядра: помилка, час, номери дублів, пік wav, експорт ffmpeg."""
from __future__ import annotations

import array
import datetime as dt
import math
import os
import re
import subprocess
import sys
import wave
from pathlib import Path

from .. import proc
from ..catalog import duration
from ..paths import MIN_TAKE_SEC, SR, STATE_DIR

PREVIEW_DIR = STATE_DIR / "preview-cache"
ORIGINALS_JSON = ".originals.json"     # у game-files/: {rel: {lang, sha256}} — файли-оригінали, їх не публікувати

TAKE_RE = re.compile(r"\.take(\d+)\.wav$", re.I)


class StudioError(Exception):
    """Помилка, яку варто показати користувачеві."""


def now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def take_no(name: str | None) -> int:
    m = TAKE_RE.search(name or "")
    return int(m.group(1)) if m else 0


def file_iso(p: Path) -> str:
    try:
        return dt.datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds")
    except OSError:
        return now()


def new_entry() -> dict:
    return {"ua_text": None, "approved": None, "original": None, "takes": [], "history": []}


AUTO_TRIM = proc.AUTO_TRIM


CLIP_LEVEL = 0.98     # |x| ≥ цього (частка повної шкали) — перевантаження
CLIP_MIN_SAMPLES = 3  # одиничний відлік — не кліппінг (передискретизація може «перестрибнути»)


def wav_peak(path: Path) -> tuple[float, int]:
    """(пік у dBFS, кількість відліків з |x| ≥ CLIP_LEVEL) для wav s16; без numpy."""
    with wave.open(str(path), "rb") as w:
        if w.getsampwidth() != 2:
            raise StudioError("очікується 16-бітний WAV")
        data = array.array("h")
        data.frombytes(w.readframes(w.getnframes()))
    if sys.byteorder == "big":
        data.byteswap()
    peak = max((max(data), -min(data)), default=0)
    limit = CLIP_LEVEL * 32768
    clipped = sum(1 for v in data if v >= limit or -v >= limit)
    return (round(20 * math.log10(peak / 32768), 2) if peak else -120.0), clipped


def export_take(src: Path, dst: Path, filters: list[str]) -> bool:
    """Копія дубля для гри: ланцюжок ffmpeg-фільтрів `filters` (через кому) → 22050 Hz mono s16.

    Порожній ланцюжок → звичайна конвертація. False — не вдалося (викликач робить просту копію).
    Фільтри збирає Service._export_filters (ручне обрізання, авто-обрізання тиші, EQ персонажа).
    """
    tmp = dst.with_suffix(".tmp.wav")
    try:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
                            *(["-af", ",".join(filters)] if filters else []),
                            "-ar", str(SR), "-ac", "1", "-sample_fmt", "s16", str(tmp)],
                           capture_output=True, timeout=30)
        if r.returncode == 0 and duration(tmp) >= MIN_TAKE_SEC:
            os.replace(tmp, dst)
            return True
    except Exception:
        pass
    tmp.unlink(missing_ok=True)
    return False
