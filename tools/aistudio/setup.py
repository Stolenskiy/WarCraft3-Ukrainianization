"""Встановлення й перевірка Fish S2-Pro: платформа, .venv-fish, ваги з Hugging Face (лише після згоди з ліцензією).

  python tools/run.py ai-setup [--accept-license] [--skip-download]     python tools/run.py ai-status
Ваги НЕ копіюються в git (models/ у .gitignore); шлях — config.fish_paths() (env WC3_FISH_MODEL або settings.json).
Усі зовнішні виклики (subprocess, мережа) йдуть через `run`/`download` — у тестах підміняються.
"""
from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

from . import config

HF_REPO = "fishaudio/s2-pro"
LICENSE_URL = "https://huggingface.co/fishaudio/s2-pro/blob/main/LICENSE.md"
FISH_SPEECH_GIT = "https://github.com/fishaudio/fish-speech"
FISH_SPEECH_COMMIT = "0f8a12e8a651062fdee9c33a894bdccd3a8513f1"
REQUIREMENTS = Path(__file__).with_name("requirements-fish.txt")
# файл → мінімальний розмір (байт); шарди додатково звіряються з model.safetensors.index.json
WEIGHT_FILES = {"config.json": 500, "codec.pth": 1_000_000_000, "model.safetensors.index.json": 1000,
                "tokenizer.json": 100_000, "tokenizer_config.json": 1000, "special_tokens_map.json": 100,
                "chat_template.jinja": 100}
MIN_TOTAL = 8_000_000_000


class SetupError(Exception):
    pass


# ---------------------------------------------------------------- платформа
def detect_platform() -> dict:
    """{os, arch, accelerator: mps|cuda|cpu, speed, warning}. Без імпорту torch (його може ще не бути)."""
    osn, arch = platform.system(), platform.machine().lower()
    if osn == "Darwin" and arch in ("arm64", "aarch64"):
        acc, speed = "mps", "помірно"
        warn = "Apple Silicon (MPS): працює, але помітно повільніше за CUDA — на коротку репліку очікуйте десятки секунд; генеруйте партіями."
    elif shutil.which("nvidia-smi"):
        acc, speed = "cuda", "швидко"
        warn = ""
    else:
        acc, speed = "cpu", "дуже повільно"
        warn = ("Без GPU (CPU): модель 4 млрд параметрів на процесорі працює дуже повільно (хвилини на репліку) і потребує багато RAM; "
                "не рекомендовано — краще машина з Apple Silicon або NVIDIA.")
    return {"os": osn, "arch": arch, "accelerator": acc, "speed": speed, "warning": warn}


# ---------------------------------------------------------------- ваги
def verify_weights(model: Path | None = None) -> dict:
    """{ok, missing: [...], bytes, problems: [...]} — наявність файлів, розміри, шарди проти index.json."""
    model = Path(model or config.fish_paths()["model"])
    missing, problems, total = [], [], 0
    for name, minsz in WEIGHT_FILES.items():
        p = model / name
        if not p.is_file():
            missing.append(name)
            continue
        total += p.stat().st_size
        if p.stat().st_size < minsz:
            problems.append(f"{name}: {p.stat().st_size} байт < {minsz} (обірване завантаження?)")
    idx = model / "model.safetensors.index.json"
    if idx.is_file():
        try:
            meta = json.loads(idx.read_text(encoding="utf-8"))
            shards = sorted(set(meta["weight_map"].values()))
            need = int(meta["metadata"]["total_size"])
        except (ValueError, KeyError, TypeError):
            shards, need = [], 0
            problems.append("model.safetensors.index.json: некоректний")
        got = 0
        for s in shards:
            sp = model / s
            if not sp.is_file():
                missing.append(s)
            else:
                got += sp.stat().st_size
        total += got
        if not missing and got < need:
            problems.append(f"шарди {got} байт < очікуваних {need}")
    if not missing and not problems and total < MIN_TOTAL:
        problems.append(f"загальний розмір {total} < {MIN_TOTAL}")
    return {"ok": not missing and not problems, "missing": missing, "problems": problems, "bytes": total, "path": str(model)}


# ---------------------------------------------------------------- стан
def venv_ok() -> bool:
    return Path(config.fish_paths()["py"]).exists()


def repo_ok() -> bool:
    return (Path(config.fish_paths()["repo"]) / "fish_speech").is_dir()


def engine_status() -> dict:
    """Для реєстру двигунів: {state: ready|missing_model|missing_env, detail}. Швидко, без запуску Python із torch."""
    if not venv_ok() or not repo_ok():
        return {"state": "missing_env", "detail": "немає .venv-fish або клона fish-speech: python tools/run.py ai-setup"}
    v = verify_weights()
    if not v["ok"]:
        return {"state": "missing_model", "detail": "ваги: " + "; ".join(v["missing"] + v["problems"])}
    return {"state": "ready", "detail": ""}


def status(deep: bool = False) -> dict:
    """Повний звіт готовності для `ai-status` і UI. deep=True — ще й `import torch, fish_speech` у .venv-fish."""
    pl, w = detect_platform(), verify_weights()
    pth = config.fish_paths()
    imports = None
    if deep and venv_ok():
        r = run([pth["py"], "-I", "-c", "import torch, fish_speech; print(torch.__version__)"], timeout=120)
        imports = r.returncode == 0
    missing = [] if venv_ok() else ["venv"]
    missing += [] if repo_ok() else ["fish-speech"]
    missing += [] if w["ok"] else ["weights"]
    missing += [] if config.has_consent() else ["consent"]
    return {"ready": not missing and imports is not False, "missing": missing, "platform": pl, "weights": w,
            "venv": venv_ok(), "repo": repo_ok(), "imports_ok": imports, "consent": config.has_consent(),
            "license_accepted": config.license_accepted("fish-s2-pro"), "license_url": LICENSE_URL, "paths": pth}


# ---------------------------------------------------------------- встановлення
def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def _step(cmd: list[str], what: str, say) -> None:
    say(f"  {what}…")
    r = run(cmd)
    if r.returncode:
        raise SetupError(f"{what}: код {r.returncode}\n{(r.stderr or r.stdout)[-400:]}")


def install_env(say=print) -> None:
    """.venv-fish (Python 3.11) + клон fish-speech на закріпленому коміті + закріплені залежності."""
    pth = config.fish_paths()
    venv_dir = Path(pth["py"]).parent.parent
    uv = shutil.which("uv")
    if not venv_ok():
        if uv:
            _step([uv, "venv", "-q", "-p", "3.11", str(venv_dir)], "створення .venv-fish", say)
        else:
            _step([sys.executable, "-m", "venv", str(venv_dir)], "створення .venv-fish (потрібен Python 3.11)", say)
    repo = Path(pth["repo"])
    if not repo.is_dir():
        if not shutil.which("git"):
            raise SetupError("потрібен git")
        _step(["git", "clone", "-q", FISH_SPEECH_GIT, str(repo)], "клонування fish-speech", say)
    _step(["git", "-C", str(repo), "checkout", "-q", FISH_SPEECH_COMMIT], f"fish-speech на {FISH_SPEECH_COMMIT[:8]}", say)
    base = [uv, "pip", "install", "-q", "--python", pth["py"]] if uv else [pth["py"], "-m", "pip", "install", "-q"]
    _step([*base, "-r", str(REQUIREMENTS), "-e", str(repo)], "встановлення залежностей", say)


def download(model: Path, say=print) -> None:
    """Ваги з Hugging Face у `model` через huggingface_hub у .venv-fish (HF_TOKEN з середовища, якщо репозиторій закритий)."""
    code = f"from huggingface_hub import snapshot_download as d; d({HF_REPO!r}, local_dir={str(model)!r})"
    _step([config.fish_paths()["py"], "-I", "-c", code], f"завантаження ваг {HF_REPO} (≈10 ГБ)", say)


def license_gate(accept: bool, ask=input, say=print) -> bool:
    """Ваги завантажуємо лише після явної згоди: прапорець або інтерактивне «yes». Без TTY і без прапорця — ні."""
    say(f"Ваги Fish S2-Pro — Fish Audio Research License (НЕкомерційна). Прочитайте: {LICENSE_URL}")
    say("Наслідок: ШІ-репліки в наших пакетах голосів ліцензуються CC BY-NC 4.0 (docs/decisions/0007-ai-lines-license.md).")
    if accept:
        return True
    if not sys.stdin.isatty():
        say("Підтвердьте ліцензію прапорцем --accept-license.")
        return False
    return ask("Приймаю ліцензію (yes/no): ").strip().lower() in ("yes", "y", "так", "т")


def setup(accept_license: bool = False, skip_download: bool = False, say=print, ask=input) -> int:
    pl = detect_platform()
    say(f"Платформа: {pl['os']} {pl['arch']}, прискорювач: {pl['accelerator']} ({pl['speed']})")
    if pl["warning"]:
        say("УВАГА: " + pl["warning"])
    try:
        install_env(say)
        model = Path(config.fish_paths()["model"])
        if verify_weights(model)["ok"]:
            say(f"Ваги вже є й перевірені: {model}")
        elif skip_download:
            say("Завантаження ваг пропущено (--skip-download).")
        else:
            if not license_gate(accept_license, ask, say):
                say("Без згоди з ліцензією ваги не завантажуємо.")
                return 2
            config.accept_license("fish-s2-pro", date.today().isoformat())
            download(model, say)
            v = verify_weights(model)
            if not v["ok"]:
                raise SetupError("ваги не пройшли перевірку: " + "; ".join(v["missing"] + v["problems"]))
            say(f"Ваги перевірено: {round(v['bytes'] / 1e9, 1)} ГБ")
    except SetupError as ex:
        say(f"ПОМИЛКА: {ex}")
        return 1
    say("Готово. Далі: python tools/run.py ai-consent --accept ; python tools/run.py ai-status")
    return 0
