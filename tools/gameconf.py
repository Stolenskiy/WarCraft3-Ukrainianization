"""Де лежить гра (корінь Warcraft III): одне місце правди для всіх інструментів. Лише stdlib.

Порядок визначення:
  1. змінна середовища WC3_GAME_ROOT;
  2. data/local/settings.json {"game_root": "..."} (gitignored; пише `set_game_root` / `run.py game-root PATH`);
  3. автопошук за ОС (macOS /Applications, Windows Program Files + реєстр Blizzard, Linux Wine/Lutris/Proton/Bottles).
Кандидат вважається коренем WC3, якщо в ньому є тека Data/ (CASC) або виконуваний файл / застосунок гри.
Якщо нічого не знайдено, `get_game_root()` повертає типовий шлях ОС (тека може не існувати: інструменти скажуть про це самі).
"""
from __future__ import annotations

import glob
import json
import os
import sys
from pathlib import Path

ENV = "WC3_GAME_ROOT"
MARKERS = (".build.info", "Warcraft III.exe", "Warcraft III Launcher.exe", "Warcraft III.app", "Warcraft III Launcher.app",
           "x86_64/Warcraft III.exe", "_retail_/x86_64/Warcraft III.exe")
REG_KEY = r"SOFTWARE\Blizzard Entertainment\Warcraft III"
MAC = ["/Applications/Warcraft III Classic", "/Applications/Warcraft III"]
WIN = [r"C:\Program Files (x86)\Warcraft III", r"C:\Program Files\Warcraft III"]
WINE_SUFFIXES = ("Program Files (x86)/Warcraft III", "Program Files/Warcraft III")


def _repo_root() -> Path:
    return Path(os.environ.get("WC3UA_ROOT") or Path(__file__).resolve().parent.parent)


def settings_path(root: Path | None = None) -> Path:
    return (root or _repo_root()) / "data/local/settings.json"


def looks_like_wc3(p: str | os.PathLike | None) -> bool:
    """Тека схожа на корінь WC3: є Data/ або виконуваний файл/застосунок гри."""
    if not p:
        return False
    p = Path(p)
    try:
        return p.is_dir() and ((p / "Data").is_dir() or any((p / m).exists() for m in MARKERS))
    except OSError:
        return False


def _winreg_paths() -> list[str]:
    """InstallPath із реєстру Blizzard (лише Windows; best effort)."""
    try:
        import winreg  # type: ignore[import-not-found]
    except ImportError:
        return []
    out: list[str] = []
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for view in (getattr(winreg, "KEY_WOW64_32KEY", 0), getattr(winreg, "KEY_WOW64_64KEY", 0)):
            try:
                with winreg.OpenKey(hive, REG_KEY, 0, winreg.KEY_READ | view) as k:
                    val = winreg.QueryValueEx(k, "InstallPath")[0]
                if val and val not in out:
                    out.append(str(val))
            except OSError:
                continue
    return out


def _wine_prefixes() -> list[Path]:
    home = Path.home()
    pats = [os.environ.get("WINEPREFIX", ""), str(home / ".wine"), str(home / "Games/*"),
            str(home / ".local/share/lutris/runners/wine/*"), str(home / ".steam/steam/steamapps/compatdata/*/pfx"),
            str(home / ".local/share/Steam/steamapps/compatdata/*/pfx"),
            str(home / ".var/app/com.usebottles.bottles/data/bottles/bottles/*"), str(home / ".local/share/bottles/bottles/*")]
    out: list[Path] = []
    for pat in filter(None, pats):
        out += [Path(m) for m in sorted(glob.glob(pat))]
    return out


def candidates() -> list[str]:
    """Типові місця за поточною ОС (від найімовірнішого)."""
    if sys.platform == "darwin":
        return list(MAC)
    if sys.platform.startswith("win"):
        return _winreg_paths() + list(WIN)
    return [str(pre / "drive_c" / s) for pre in _wine_prefixes() for s in WINE_SUFFIXES]


def _saved(root: Path | None = None) -> str:
    try:
        return str(json.loads(settings_path(root).read_text(encoding="utf-8")).get("game_root") or "")
    except (OSError, ValueError, AttributeError):
        return ""


def default_root() -> str:
    """Що показати, коли гру не знайдено."""
    if sys.platform == "darwin":
        return MAC[0]
    return WIN[0] if sys.platform.startswith("win") else str(Path.home() / ".wine/drive_c" / WINE_SUFFIXES[0])


def resolve(root: Path | None = None) -> tuple[str, str, bool]:
    """(шлях, джерело: env|settings|auto|default, чи схожий на гру)."""
    env = os.environ.get(ENV, "").strip()
    if env:
        return env, "env", looks_like_wc3(env)
    saved = _saved(root)
    if saved:
        return saved, "settings", looks_like_wc3(saved)
    for c in candidates():
        if looks_like_wc3(c):
            return c, "auto", True
    return default_root(), "default", False


def get_game_root(root: Path | None = None) -> Path:
    return Path(resolve(root)[0])


def set_game_root(path: str | os.PathLike, root: Path | None = None) -> Path:
    """Перевіряє й зберігає в data/local/settings.json. Невалідний шлях → ValueError, файл не чіпаємо."""
    p = Path(os.path.expanduser(str(path)))
    if not looks_like_wc3(p):
        raise ValueError(f"не схоже на теку Warcraft III (потрібна Data/ або виконуваний файл гри): {p}")
    f = settings_path(root)
    try:
        cur = json.loads(f.read_text(encoding="utf-8"))
        cur = cur if isinstance(cur, dict) else {}
    except (OSError, ValueError):
        cur = {}
    cur["game_root"] = str(p)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(cur, indent=2, ensure_ascii=False), encoding="utf-8")
    return p


def describe(root: Path | None = None) -> dict:
    path, source, valid = resolve(root)
    return {"path": path, "source": source, "valid": valid, "platform": sys.platform,
            "env_overrides": bool(os.environ.get(ENV, "").strip())}
