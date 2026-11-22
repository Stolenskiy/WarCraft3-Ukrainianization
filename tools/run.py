#!/usr/bin/env python3
"""Кросплатформний запуск (macOS / Linux / Windows без make): `python tools/run.py <команда>`.

  setup [--dev-only]      .venv (Python 3.11) + залежності + git-хуки (--dev-only: лише requirements-dev)
  doctor                  чого бракує в середовищі
  verify                  lint + guard + check-voices + швидкі тести (без Chrome)
  check                   verify + усі тести з Chrome і покриттям (те, що робить CI)
  test                    усі тести з покриттям
  studio [--port N] [--no-browser]
  install-voices [--apply]    план або встановлення голосів у гру;  uninstall-voices
  publish-voice --author НІК --consent
  check-voices | transcripts-local | refs
  game-root [ШЛЯХ]        показати або зберегти теку гри (data/local/settings.json)
  docker [аргументи]      `docker compose up --build` (студія в контейнері, http://127.0.0.1:8765)

Лише stdlib. Команди — ті самі Python-скрипти/pytest, що й у Makefile; інтерпретатор — .venv (bin або Scripts).
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))   # `python -I` не додає теку скрипта
ROOT = HERE.parent

# Мають збігатися з Makefile (CORE_TESTS_A/B) — це перевіряє tests/test_run.py.
CORE_TESTS_A = ["tests/test_studio_core.py", "tests/test_eq.py", "tests/test_install_voices.py", "tests/test_guard_no_audio.py",
                "tests/test_docs_sync.py", "tests/test_doctor.py"]
CORE_TESTS_B = ["tests/test_studio_proc.py", "tests/test_voices.py"]
# нове (кросплатформа) — теж швидке, входить у verify
CORE_TESTS_C = ["tests/test_gameconf.py", "tests/test_windows.py", "tests/test_run.py"]


def is_windows() -> bool:
    return sys.platform.startswith("win")


def venv_python() -> Path:
    return ROOT / (".venv/Scripts/python.exe" if is_windows() else ".venv/bin/python")


def py() -> list[str]:
    """Інтерпретатор для скриптів проєкту: .venv, інакше поточний (з попередженням)."""
    v = venv_python()
    if v.exists():
        return [str(v), "-I"]
    print("УВАГА: .venv немає — використовую поточний Python. Виконайте: python tools/run.py setup", file=sys.stderr)
    return [sys.executable, "-I"]


def child_env() -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault("PYTHONUTF8", "1")           # кирилиця у файлах і консолі на Windows (cp1251/cp1252)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env


def _call(cmd: list[str]) -> int:
    return subprocess.run(cmd, cwd=ROOT, env=child_env()).returncode


def _parallel(cmds: list[list[str]]) -> int:
    procs = [subprocess.Popen(c, cwd=ROOT, env=child_env()) for c in cmds]
    return int(any(p.wait() for p in procs))


def _steps(*cmds: list[str]) -> int:
    rc = 0
    for c in cmds:
        rc = _call(c)
        if rc:
            return rc
    return 0


def lint_cmds() -> list[list[str]]:
    node = shutil.which("node") or "node"
    return [[*py(), "-m", "ruff", "check", "."], [node, "--check", "tools/studio/web/app.js"], [node, "--check", "tools/studio/web/ai.js"]]


def cheap_cmds() -> list[list[str]]:
    return [*lint_cmds(), [*py(), "tools/guard_no_audio.py"], [*py(), "tools/check_voices.py"]]


def cmd_verify(_a) -> int:
    rc = _steps(*cheap_cmds())
    if rc:
        return rc
    return _parallel([[*py(), "-m", "pytest", "-q", *g] for g in (CORE_TESTS_A, CORE_TESTS_B, CORE_TESTS_C)])


def cmd_check(_a) -> int:
    return _steps(*cheap_cmds(), [*py(), "-m", "pytest", "-q", "-s", "--cov"])


def cmd_test(_a) -> int:
    return _call([*py(), "-m", "pytest", "-q", "-s", "--cov"])


def _find_py311() -> list[str] | None:
    for cand in (["python3.11"], ["py", "-3.11"], ["python"], [sys.executable]):
        if not shutil.which(cand[0]) and cand[0] != sys.executable:
            continue
        r = subprocess.run([*cand, "-c", "import sys;print('%d.%d' % sys.version_info[:2])"], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip() == "3.11":
            return cand
    return None


def cmd_setup(a) -> int:
    v = venv_python()
    uv = shutil.which("uv")
    if not v.exists():
        if uv:
            rc = _call([uv, "venv", "-q", "-p", "3.11", ".venv"])
        else:
            base = _find_py311()
            if not base:
                print("Потрібен Python 3.11 (або uv). Windows: winget install astral-sh.uv ; macOS: brew install uv ; Linux: apt install python3.11 python3.11-venv")
                return 1
            rc = _call([*base, "-m", "venv", ".venv"])
        if rc:
            return rc
    reqs = ["requirements-dev.txt"] + ([] if a.dev_only else ["requirements.txt"])
    for r in reqs:
        cmd = [uv, "pip", "install", "-q", "--python", str(v), "-r", r] if uv else [str(v), "-m", "pip", "install", "-q", "-r", r]
        rc = _call(cmd)
        if rc:
            return rc
    if not a.dev_only and (ROOT / ".git").exists() and shutil.which("git"):
        _call(["git", "config", "core.hooksPath", ".githooks"])
    print("Готово. Далі: python tools/run.py doctor")
    return 0


def cmd_doctor(_a) -> int:
    return _call([sys.executable, "-I", "tools/doctor.py"])     # системний python: працює й до setup


def cmd_studio(a) -> int:
    extra = (["--port", str(a.port)] if a.port else []) + (["--no-browser"] if a.no_browser else [])
    return _call([*py(), "tools/record_studio.py", *extra])


def cmd_install(a) -> int:
    return _call([*py(), "tools/install_voices.py", *(["--apply"] if a.apply else [])])


def cmd_uninstall(_a) -> int:
    return _call([*py(), "tools/install_voices.py", "--uninstall"])


def cmd_publish(a) -> int:
    if not a.author:
        print("Потрібно --author <нік> (і --consent: це мій власний голос, CC BY 4.0)")
        return 2
    return _call([*py(), "tools/voices.py", "publish", "--author", a.author, *(["--consent"] if a.consent else [])])


def cmd_check_voices(_a) -> int:
    return _call([*py(), "tools/check_voices.py"])


def cmd_transcripts(_a) -> int:
    return _call([*py(), "tools/split_transcripts.py"])


def cmd_refs(_a) -> int:
    return _call([*py(), "tools/build_refs.py"])


def cmd_game_root(a) -> int:
    import gameconf
    if a.path:
        try:
            p = gameconf.set_game_root(a.path)
        except ValueError as ex:
            print(ex)
            return 1
        print(f"Збережено: {p}  ({gameconf.settings_path()})")
        return 0
    d = gameconf.describe()
    print(f"Тека гри: {d['path']}\n  джерело: {d['source']}   схожа на Warcraft III: {'так' if d['valid'] else 'НІ'}")
    if not d["valid"]:
        print("  Вкажіть: python tools/run.py game-root <шлях>  (або змінна WC3_GAME_ROOT)")
    return 0 if d["valid"] else 1


def cmd_docker(a) -> int:
    if not shutil.which("docker"):
        print("Docker не знайдено. Встановіть Docker Desktop (або docker engine + compose plugin) і запустіть його.")
        return 1
    return _call(["docker", "compose", *(a.args or ["up", "--build"])])


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="run.py", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name, fn, help_):
        sp = sub.add_parser(name, help=help_)
        sp.set_defaults(fn=fn)
        return sp

    add("setup", cmd_setup, "venv + залежності + хуки").add_argument("--dev-only", action="store_true")
    add("doctor", cmd_doctor, "перевірка середовища")
    add("verify", cmd_verify, "швидка перевірка (без Chrome)")
    add("check", cmd_check, "як у CI")
    add("test", cmd_test, "усі тести + покриття")
    s = add("studio", cmd_studio, "студія запису")
    s.add_argument("--port", type=int)
    s.add_argument("--no-browser", action="store_true")
    add("install-voices", cmd_install, "голоси в гру (план; --apply — встановити)").add_argument("--apply", action="store_true")
    add("uninstall-voices", cmd_uninstall, "відкат встановлених голосів")
    p = add("publish-voice", cmd_publish, "дублі → voices/<нік>/")
    p.add_argument("--author")
    p.add_argument("--consent", action="store_true")
    add("check-voices", cmd_check_voices, "перевірка пакетів voices/")
    add("transcripts-local", cmd_transcripts, "тексти оригіналів → data/local/")
    add("refs", cmd_refs, "оригінали з гри → reference-en/")
    add("game-root", cmd_game_root, "показати/задати теку гри").add_argument("path", nargs="?")
    add("docker", cmd_docker, "студія в Docker").add_argument("args", nargs="*")
    return ap


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
