#!/usr/bin/env python3
"""Перевірка середовища (`make doctor`): що потрібно для verify / check / студії / оригіналів, підказки зі встановлення.
Лише stdlib; запускається системним python3, тож працює й до `make setup-dev`."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAC = sys.platform == "darwin"
CHROME_APP = Path("/Applications/Google Chrome.app")


def _run(*cmd) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        return (r.stdout + r.stderr).strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def checks() -> list[tuple[str, str, bool, str]]:
    """(назва, потрібно для, обов'язково?, підказка) для кожної відсутньої залежності; ok-рядки мають hint == ''."""
    out = []
    venv_py = ROOT / ".venv/bin/python"
    ver = _run(str(venv_py), "-c", "import sys;print('%d.%d' % sys.version_info[:2])") if venv_py.exists() else ""
    have_py311 = bool(shutil.which("python3.11"))
    have_uv = bool(shutil.which("uv"))
    out.append(("Python 3.11 або uv", "make setup-dev", True,
                "" if have_py311 or have_uv else "brew install uv   (або python@3.11)"))
    out.append((".venv на Python 3.11", "усі make-цілі", True,
                "" if ver == "3.11" else "make setup-dev" + (f"   (зараз {ver})" if ver else "")))
    out.append(("ffmpeg", "тести обробки, студія", True,
                "" if shutil.which("ffmpeg") else "brew install ffmpeg   (Linux: apt install ffmpeg)"))
    out.append(("node", "make lint (node --check app.js)", True,
                "" if shutil.which("node") else "brew install node   (Linux: apt install nodejs)"))
    chrome = CHROME_APP.exists() or any(shutil.which(c) for c in ("google-chrome", "google-chrome-stable", "chrome"))
    pw = bool(venv_py.exists() and _run(str(venv_py), "-c", "import playwright;print(1)") == "1")
    out.append(("Google Chrome + playwright", "e2e-тести студії (make test/check; без них — skip локально)", False,
                "" if chrome and pw else "встановити Chrome; playwright: make setup-dev"))
    out.append(("PyCASC", "make refs (оригінали з гри)", False,
                "" if venv_py.exists() and _run(str(venv_py), "-c", "import PyCASC;print(1)") == "1"
                else "make setup-refs"))
    hooks = _run("git", "-C", str(ROOT), "config", "core.hooksPath")
    out.append(("git-хуки", "pre-commit: guard + ruff", False, "" if hooks == ".githooks" else "make hooks"))
    return out


def main() -> int:
    bad = 0
    for name, need, required, hint in checks():
        if not hint:
            print(f"  ok   {name}")
        else:
            print(f"  {'НЕМАЄ' if required else 'бажано'}  {name} — {need}\n         → {hint}")
            bad += required
    print("Усе потрібне для `make verify` є." if not bad else f"Бракує обов'язкового: {bad}.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
