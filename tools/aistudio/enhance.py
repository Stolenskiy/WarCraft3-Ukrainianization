"""ШІ-очищення власних дублів: Sidon (ONNX) прибирає луну кімнати й шум, відновлює «близький» звук; потім гучність.

  python tools/run.py enhance-setup        .venv-enhance (onnxruntime, без torch) + ваги ≈ 290 МБ у models/sidon-onnx
Модель: Sidon v0.1 (sarulab-speech, MIT; arXiv 2509.17052) в ONNX-експорті soniqo/Sidon-ONNX (MIT), int8 лише ваг.
Результат — ВАШ запис (модель не генерує голос із тексту), тож ліцензія дубля — авторська, як і в інших дублів.
Усі зовнішні виклики (subprocess, мережа) — через параметри `run` / WorkerRunner: у тестах підміняються.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from studio.paths import ROOT, SR

ENGINE = "sidon-v0.1"
TITLE = "Sidon v0.1 — прибрати луну й шум"
LICENSE, LICENSE_URL = "MIT", "https://huggingface.co/soniqo/Sidon-ONNX"
HF_REPO, HF_REVISION = "soniqo/Sidon-ONNX", "a6dce244cbcd0361ef79c030e246e6f9671770c1"
FRONTEND_REPO, FRONTEND_REVISION = "facebook/w2v-bert-2.0", "da985ba0987f70aaeb84a80f2851cfac8c697a7b"
REQUIREMENTS = Path(__file__).with_name("requirements-enhance.txt")
WORKER = Path(__file__).resolve().parents[1] / "ai_engines/sidon_worker.py"   # код, не дані: не від WC3UA_ROOT
MODEL_FILES = {"int8/sidon-predictor.onnx": 150_000_000, "int8/sidon-vocoder.onnx": 80_000_000,
               "frontend/preprocessor_config.json": 100}
DOWNLOAD_MB = 290
TARGET_LUFS = -16.0           # «ближче й гучніше»: рівень мовлення як у подкасті; у гру однаково йде «як в оригіналі»
GAIN_MIN, GAIN_MAX = -12.0, 18.0
LIMIT = "alimiter=limit=0.891:level=0"      # стеля −1 дБFS
TIMING_DEFAULTS = {"load": 4.0, "per": 1.0, "metrics": 0.0}   # с: виміряно на Apple Silicon (CPU) — 0.4–0.8 с на 2–4 с дубля

DL_SCRIPT = """import sys
from huggingface_hub import snapshot_download
out = sys.argv[1]
snapshot_download(sys.argv[2], revision=sys.argv[3], allow_patterns=["int8/*", "config.json", "README.md"], local_dir=out)
snapshot_download(sys.argv[4], revision=sys.argv[5], allow_patterns=["preprocessor_config.json"], local_dir=out + "/frontend")
"""


class EnhanceError(Exception):
    pass


def paths() -> dict:
    root = Path(os.environ.get("WC3UA_ROOT") or ROOT)
    venv = root / ".venv-enhance"
    py = venv / ("Scripts/python.exe" if sys.platform.startswith("win") else "bin/python")
    return {"venv": venv, "py": Path(os.environ.get("WC3_ENHANCE_PY") or py),
            "model": Path(os.environ.get("WC3_ENHANCE_MODEL") or root / "models/sidon-onnx")}


def missing_files(model: Path | None = None) -> list[str]:
    model = Path(model or paths()["model"])
    return [n for n, size in MODEL_FILES.items() if not (model / n).is_file() or (model / n).stat().st_size < size]


def status() -> dict:
    """{state: ready|missing_env|missing_model, detail, engine, title, license, license_url, download_mb}."""
    p = paths()
    info = {"engine": ENGINE, "title": TITLE, "license": LICENSE, "license_url": LICENSE_URL, "download_mb": DOWNLOAD_MB}
    if not p["py"].is_file():
        return {**info, "state": "missing_env", "detail": "немає .venv-enhance: python tools/run.py enhance-setup"}
    miss = missing_files(p["model"])
    if miss:
        return {**info, "state": "missing_model", "detail": "ваги: " + ", ".join(miss)}
    return {**info, "state": "ready", "detail": ""}


def setup(say=print, run=subprocess.run, uv: str | None = None) -> dict:
    """Створює .venv-enhance (uv, якщо є; інакше venv поточного Python), ставить закріплені залежності, качає ваги."""
    p, uv = paths(), uv if uv is not None else shutil.which("uv")

    def sh(cmd: list[str], what: str) -> None:
        say(what)
        r = run([str(c) for c in cmd], capture_output=True, text=True)
        if r.returncode != 0:
            raise EnhanceError(f"{what}: {(r.stderr or r.stdout or '').strip()[-400:] or 'помилка'}")

    if not p["py"].is_file():
        sh([uv, "venv", "--python", "3.11", p["venv"]] if uv else [sys.executable, "-m", "venv", p["venv"]], "створюю .venv-enhance")
    sh([uv, "pip", "install", "--python", p["py"], "-r", REQUIREMENTS] if uv else [p["py"], "-m", "pip", "install", "-r", REQUIREMENTS],
       "ставлю onnxruntime, numpy, soundfile, soxr, transformers (без torch)")
    if missing_files(p["model"]):
        p["model"].mkdir(parents=True, exist_ok=True)
        sh([p["py"], "-I", "-c", DL_SCRIPT, p["model"], HF_REPO, HF_REVISION, FRONTEND_REPO, FRONTEND_REVISION],
           f"качаю модель Sidon (≈ {DOWNLOAD_MB} МБ, MIT) з Hugging Face")
    st = status()
    if st["state"] != "ready":
        raise EnhanceError(f"після встановлення: {st['detail']}")
    say("готово: ШІ-очищення запису доступне")
    return st


# ---------------------------------------------------------------- гучність і формат гри
def loudness(path: Path) -> float | None:
    """Інтегрована гучність (LUFS, ffmpeg ebur128); None — тиша / не вдалося."""
    try:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128=framelog=quiet", "-f", "null", "-"],
                           capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)
    v = float(m[-1]) if m else None
    return v if v is not None and v > -70 else None


def finish(raw: Path, target: Path) -> float:
    """48 кГц вихід моделі → 22050 Гц mono s16 (формат дублів) на рівні TARGET_LUFS з лімітером. Повертає підсилення, дБ."""
    lu = loudness(raw)
    gain = 0.0 if lu is None else max(GAIN_MIN, min(GAIN_MAX, TARGET_LUFS - lu))
    tmp = target.with_suffix(".tmp.wav")
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(raw), "-af", f"volume={gain:.2f}dB,{LIMIT}",
                        "-ar", str(SR), "-ac", "1", "-sample_fmt", "s16", str(tmp)], capture_output=True, timeout=120)
    if r.returncode != 0 or not tmp.is_file():
        tmp.unlink(missing_ok=True)
        raise EnhanceError("ffmpeg не зміг зберегти очищений дубль")
    os.replace(tmp, target)
    return round(gain, 1)
