"""ШІ-варіанти: автотривалість (темп під довжину оригіналу) і автовибір (оцінка й рейтинг варіантів).

Автотривалість не змінює файл варіанта: «Взяти в дублі» з `fit` ставить новому дублю `tempo` (той самий atempo, що й ⏩ Темп
дубля, — висота голосу не змінюється). Ціль — тривалість ГОЛОСУ оригіналу (оригінал без тиші на краях тим самим AUTO_TRIM,
що обрізає й ШІ-варіант; якщо оригіналу немає — `duration` з data/transcripts-*.json). Темп лише в межах FIT_MIN–FIT_MAX:
далі прискорення чути як «бурмотіння», тож фраза, що не влазить, лишається довшою, а UI пояснює чому.

Оцінка 0–100 (більше — краще): зважене середнє наявних складових — розбірливість (CER), схожість голосу, тривалість
відносно оригіналу (після підгонки темпу) і запас до перевантаження. Невідома метрика (null) не враховується.
"""
from __future__ import annotations

import math
import tempfile
from pathlib import Path

from .catalog import duration
from .svc.util import AUTO_TRIM, CLIP_MIN_SAMPLES, export_take, wav_peak

FIT_MIN, FIT_MAX = 0.8, 1.25     # розумний діапазон темпу для ШІ (у межах темпу дубля proc.TEMPO_MIN–TEMPO_MAX)
FIT_TOL = 0.04                   # ±4 % — «як в оригіналі», темп не чіпаємо
WEIGHTS = {"cer": 0.45, "similarity": 0.25, "dur": 0.2, "clip": 0.1}
_span: dict[tuple[str, int], float | None] = {}


def voice_dur(path: Path) -> float | None:
    """Тривалість голосу (без тиші на краях, AUTO_TRIM) будь-якого аудіо; кеш за (шлях, mtime)."""
    try:
        key = (str(path), path.stat().st_mtime_ns)
    except OSError:
        return None
    if key not in _span:
        with tempfile.TemporaryDirectory(prefix="wc3ua-fit-") as td:
            out = Path(td) / "v.wav"
            _span[key] = round(duration(out), 3) if export_take(path, out, [AUTO_TRIM]) else None
    return _span[key]


def target_dur(ln) -> float | None:
    """Ціль автотривалості для репліки: голос оригіналу, інакше тривалість із транскрипту; None — невідомо."""
    d = voice_dur(ln.ref_path)
    return d if d else (round(ln.ru_dur, 3) if ln.ru_dur > 0 else None)


def fit(dur: float | None, target: float | None) -> dict | None:
    """Темп під тривалість оригіналу: {target, need, tempo, after, fits, short, note}; None — тривалості невідомі."""
    if not dur or not target:
        return None
    need = dur / target
    tempo = 1.0 if abs(need - 1) <= FIT_TOL else min(FIT_MAX, max(FIT_MIN, need))
    after = dur / tempo
    fits, short = after <= target * (1 + FIT_TOL), after < target * (1 - FIT_TOL)
    if tempo == 1.0:
        note = f"довжина як в оригіналі ({target:.2f} с) — темп не потрібен"
    elif not fits:
        note = (f"не влазить: щоб збігтися з оригіналом ({target:.2f} с), треба ×{need:.2f}, а розумна межа ×{FIT_MAX:.2f} — "
                f"буде {after:.2f} с (+{after - target:.2f} с). Скоротіть текст або згенеруйте ще варіант")
    elif short:
        note = f"коротший за оригінал навіть після сповільнення ×{FIT_MIN:.2f}: {after:.2f} с проти {target:.2f} с — у грі це не заважає"
    else:
        note = f"темп ×{tempo:.2f} → {after:.2f} с, як оригінал ({target:.2f} с); висота голосу та сама"
    return {"target": round(target, 3), "need": round(need, 3), "tempo": round(tempo, 3), "after": round(after, 3),
            "fits": fits, "short": short, "note": note}


def peak_meta(wav: Path) -> dict:
    """Пік і перевантаження варіанта — для побічного json (оцінка «кліпінг/пік»)."""
    try:
        peak_db, n_clip = wav_peak(wav)
    except Exception:      # noqa: BLE001 — не wav s16 / не читається: метрика просто невідома
        return {"peak_db": None, "clipped": None}
    return {"peak_db": peak_db, "clipped": n_clip >= CLIP_MIN_SAMPLES}


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def parts(v: dict, f: dict | None) -> dict:
    """Складові оцінки 0..1 (лише відомі)."""
    out = {}
    if v.get("cer") is not None:
        out["cer"] = _clamp(1 - min(float(v["cer"]), 0.5) / 0.5)              # CER 0 → 1, ≥ 50 % → 0
    if v.get("similarity") is not None:
        out["similarity"] = _clamp((float(v["similarity"]) - 0.6) / 0.35)    # косинус x-vector: ≤ 0.6 → 0, ≥ 0.95 → 1
    if f:
        stretch = abs(math.log(f["tempo"])) / math.log(FIT_MAX) * 0.3        # сильне розтягування трохи псує звук
        res = math.log(f["after"] / f["target"])
        miss = max(0.0, abs(res) - math.log(1 + FIT_TOL)) / (math.log(1.5) if res > 0 else math.log(2))   # задовго — гірше, ніж закоротко
        out["dur"] = _clamp(1 - stretch - miss)
    if v.get("clipped") is not None:
        out["clip"] = 0.0 if v["clipped"] else 0.5 if (v.get("peak_db") or -120) > -0.1 else 1.0
    return {k: round(x, 3) for k, x in out.items()}


def score(p: dict) -> int | None:
    w = sum(WEIGHTS[k] for k in p)
    return round(100 * sum(WEIGHTS[k] * x for k, x in p.items()) / w) if w else None


def rank(variants: list[dict], target) -> list[dict]:
    """Доповнює кожен варіант: fit, score, score_parts, rank (1 — найкращий), best (лише коли є з чим порівнювати).
    `target` — секунди або функція (рахується лише якщо варіанти є). Повертає той самий список."""
    if not variants:
        return variants
    t = target() if callable(target) else target
    for v in variants:
        v["fit"] = fit(v.get("dur"), t)
        v["score_parts"] = parts(v, v["fit"])
        v["score"] = score(v["score_parts"])
    order = sorted((v for v in variants if v["score"] is not None), key=lambda v: (-v["score"], v.get("n") or 0))
    for v in variants:
        v["rank"], v["best"] = None, False
    for i, v in enumerate(order, 1):
        v["rank"] = i
    if len(order) >= 2:
        order[0]["best"] = True
    return variants


def best(variants: list[dict]) -> dict | None:
    return next((v for v in variants if v.get("rank") == 1), None)
