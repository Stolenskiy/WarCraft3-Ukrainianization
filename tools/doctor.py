#!/usr/bin/env python3
"""Перевірка середовища (`make doctor`): що потрібно для verify / check / студії / оригіналів, підказки зі встановлення.
Лише stdlib; запускається системним python3, тож працює й до `make setup-dev`."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))   # `python -I` не додає теку скрипта
import gameconf  # noqa: E402

CHROME_APP = Path("/Applications/Google Chrome.app")
REG_PATH = r"HKCU\Software\Blizzard Entertainment\Warcraft III"
REG_VALUE = "Allow Local Files"
REG_ADD = f'reg add "{REG_PATH}" /v "{REG_VALUE}" /t REG_DWORD /d 1 /f'
MAC_DEFAULTS = 'defaults write "com.blizzard.WarcraftIII" "Allow Local Files" -int 1'


def is_windows() -> bool:
    return sys.platform.startswith("win")


def venv_python() -> Path:
    return ROOT / (".venv/Scripts/python.exe" if is_windows() else ".venv/bin/python")


def _run(*cmd) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        return (r.stdout + r.stderr).strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def browser_paths() -> list[Path]:
    """Chrome/Edge у типових місцях Windows (Edge на Chromium теж підходить для студії)."""
    env = os.environ
    bases = [env.get(k) for k in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA")]
    rel = (("Google", "Chrome", "Application", "chrome.exe"), ("Microsoft", "Edge", "Application", "msedge.exe"))
    return [Path(b, *r) for b in bases if b for r in rel]


def allow_local_files() -> bool | None:
    """Windows: HKCU\\Software\\Blizzard Entertainment\\Warcraft III → «Allow Local Files» == 1 (лише читання).
    None — не вдалося перевірити (немає winreg / ключа). macOS: defaults read."""
    if is_windows():
        try:
            import winreg  # type: ignore[import-not-found]
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH.split("\\", 1)[1]) as k:
                return int(winreg.QueryValueEx(k, REG_VALUE)[0]) == 1
        except (ImportError, OSError, ValueError):
            return None
    if sys.platform == "darwin":
        out = _run("defaults", "read", "com.blizzard.WarcraftIII", REG_VALUE)
        return None if not out else out == "1"
    return None


def checks() -> list[tuple[str, str, bool, str]]:
    """(назва, потрібно для, обов'язково?, підказка) для кожної відсутньої залежності; ok-рядки мають hint == ''."""
    out = []
    win, mac = is_windows(), sys.platform == "darwin"
    venv_py = venv_python()
    ver = _run(str(venv_py), "-c", "import sys;print('%d.%d' % sys.version_info[:2])") if venv_py.exists() else ""
    have_py311 = bool(shutil.which("python3.11")) or (win and bool(shutil.which("py")))
    have_uv = bool(shutil.which("uv"))
    install_py = ("winget install astral-sh.uv   (або winget install Python.Python.3.11 / choco install python311)" if win
                  else "brew install uv   (або python@3.11)" if mac else "apt install python3.11 python3.11-venv   (або pipx install uv)")
    out.append(("Python 3.11 або uv", "run.py setup", True, "" if have_py311 or have_uv else install_py))
    out.append((".venv на Python 3.11", "усі команди run.py / make-цілі", True,
                "" if ver == "3.11" else "python tools/run.py setup" + (f"   (зараз {ver})" if ver else "")))
    ff = ("winget install Gyan.FFmpeg   (або choco install ffmpeg; потім перезапустіть термінал)" if win
          else "brew install ffmpeg" if mac else "apt install ffmpeg")
    out.append(("ffmpeg", "тести обробки, студія", True, "" if shutil.which("ffmpeg") else ff))
    out.append(("node", "lint (node --check web/js/*.js)", True,
                "" if shutil.which("node") else ("winget install OpenJS.NodeJS.LTS" if win else "brew install node   (Linux: apt install nodejs)")))
    if win:
        chrome = any(p.exists() for p in browser_paths())
    else:
        chrome = CHROME_APP.exists() or any(shutil.which(c) for c in ("google-chrome", "google-chrome-stable", "chrome"))
    pw = bool(venv_py.exists() and _run(str(venv_py), "-c", "import playwright;print(1)") == "1")
    out.append(("Google Chrome / Edge + playwright" if win else "Google Chrome + playwright",
                "студія в браузері; e2e-тести (без них — skip локально)", False,
                "" if chrome and pw else "встановити Chrome (або Edge); playwright: python tools/run.py setup"))
    out.append(("PyCASC", "run.py refs / make refs (оригінали з гри)", False,
                "" if venv_py.exists() and _run(str(venv_py), "-c", "import PyCASC;print(1)") == "1"
                else "python tools/run.py setup   (або make setup-refs)"))
    gd = gameconf.describe()
    out.append((f"тека гри ({gd['source']}: {gd['path']})", "встановлення голосів, make refs", False,
                "" if gd["valid"] else "python tools/run.py game-root <шлях>   (або змінна WC3_GAME_ROOT)"))
    alf = allow_local_files()
    if win or mac:
        out.append(("«Allow Local Files» = 1", "гра бере наші файли поверх CASC", False,
                    "" if alf else (REG_ADD if win else MAC_DEFAULTS) + "   (doctor нічого не пише сам)"))
    local = list((ROOT / "data/local").glob("transcripts-*.json"))
    out.append(("тексти оригіналів (data/local/)", "текст реплік у студії (інакше плейсхолдер)", False,
                "" if local else "python tools/run.py transcripts-local (є старі тексти в data/) або refs + transcribe"))
    hooks = _run("git", "-C", str(ROOT), "config", "core.hooksPath")
    out.append(("git-хуки", "pre-commit: guard + ruff", False, "" if hooks == ".githooks" else "make hooks   (Windows: git config core.hooksPath .githooks)"))
    return out


def main() -> int:
    bad = 0
    for name, need, required, hint in checks():
        if not hint:
            print(f"  ok   {name}")
        else:
            print(f"  {'НЕМАЄ' if required else 'бажано'}  {name} — {need}\n         → {hint}")
            bad += required
    print("Усе потрібне для verify є." if not bad else f"Бракує обов'язкового: {bad}.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
