"""Обробка звуку для файлу гри: налаштування, ланцюжок фільтрів, вирівнювання гучності, кеш «Як у грі».

Єдиний ланцюжок (Service._export_filters збирає його саме в такому порядку):
    ручне обрізання (atrim) → авто-обрізання тиші (AUTO_TRIM) → шумоговорення (DENOISE)
    → темп (atempo) → EQ персонажа → вирівнювання гучності (volume + alimiter, ЗАВЖДИ останнім).
Той самий ланцюжок використовують затвердження, перезапис і попереднє прослуховування «Як у грі».
Налаштування (data/studio/settings.json, не в git): {"auto_trim": true, "denoise": false, "loudness": true}.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

DEFAULT_SETTINGS = {"auto_trim": True, "denoise": False, "loudness": True}

# Тиша на краях (поріг −45 дБ RMS) — те саме, що рахує voiceSpan у web/js/wave.js.
AUTO_TRIM = ("silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.08,areverse,"
             "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.12,areverse")
# Помірне шумоговорення: afftdn гасить стаціонарний шум не більше ніж на 10 дБ (тож «водянистих»
# артефактів на мові немає; шум −45 дБ RMS падає на ≈8 дБ, тон не змінюється), adeclick прибирає клацання.
DENOISE = ["afftdn=nf=-45:nr=10", "adeclick"]
TEMPO_MIN, TEMPO_MAX = 0.8, 1.3
GAIN_LIMIT_DB = 18.0                        # підсилення/приглушення не більше ±18 дБ
LIMITER = "alimiter=limit=0.97:level=0"     # стеля 0.97 (≈ −0.26 дБFS), без авто-нормалізації рівня
PREVIEW_MAX = 200                           # файлів у data/studio/preview-cache/


class SettingsStore:
    """data/studio/settings.json: читається при кожному зверненні (файл крихітний), пишеться атомарно."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def get(self) -> dict:
        out = dict(DEFAULT_SETTINGS)
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            out.update({k: raw[k] for k in DEFAULT_SETTINGS if isinstance(raw.get(k), bool)})
        except (OSError, ValueError):
            pass
        return out

    def update(self, patch: dict) -> dict:
        if not isinstance(patch, dict):
            raise ValueError("очікується об'єкт налаштувань")
        for k, v in patch.items():
            if k not in DEFAULT_SETTINGS:
                raise ValueError(f"невідоме налаштування {k}")
            if not isinstance(v, bool):
                raise ValueError(f"налаштування {k} має бути true/false")
        cur = {**self.get(), **patch}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".tmp-", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(cur, f, indent=2)
        os.replace(tmp, self.path)
        return cur


def tempo_filter(tempo: float | None) -> list[str]:
    return [f"atempo={tempo:.4f}"] if tempo and abs(tempo - 1.0) > 1e-6 else []


_MEAN = re.compile(r"mean_volume:\s*(-?[\d.]+|-inf) dB")


def mean_volume(src: Path, filters: list[str]) -> float | None:
    """Середня гучність (дБ) результату `filters` над `src` (ffmpeg volumedetect); None — не вдалося/тиша."""
    chain = ",".join([*filters, "volumedetect"])
    try:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(src), "-af", chain, "-f", "null", "-"],
                           capture_output=True, timeout=30, text=True)
    except (OSError, subprocess.SubprocessError):
        return None
    m = _MEAN.search(r.stderr or "")
    return float(m.group(1)) if r.returncode == 0 and m and m.group(1) != "-inf" else None


_ref_cache: dict[tuple[str, int], float | None] = {}


def ref_loudness(ref: Path) -> float | None:
    """Гучність озвученої частини оригіналу (без тиші на краях); кеш за (шлях, mtime)."""
    try:
        key = (str(ref), ref.stat().st_mtime_ns)
    except OSError:
        return None
    if key not in _ref_cache:
        _ref_cache[key] = mean_volume(ref, [AUTO_TRIM])
    return _ref_cache[key]


def volume_stage(src: Path, pre: list[str], ref: Path) -> list[str]:
    """Фільтри вирівнювання гучності: gain = гучність оригіналу − гучність дубля після `pre` (±18 дБ)
    і лімітер. Порожньо, якщо щось виміряти не вдалося."""
    target, have = ref_loudness(ref), mean_volume(src, pre)
    if target is None or have is None:
        return []
    gain = max(-GAIN_LIMIT_DB, min(GAIN_LIMIT_DB, target - have))
    return [f"volume={gain:.2f}dB", LIMITER]


def evict_oldest(folder: Path, keep: int = PREVIEW_MAX) -> None:
    files = sorted((p for p in folder.glob("*.wav") if p.is_file()), key=lambda p: p.stat().st_mtime)
    for p in files[:max(0, len(files) - keep)]:
        p.unlink(missing_ok=True)
