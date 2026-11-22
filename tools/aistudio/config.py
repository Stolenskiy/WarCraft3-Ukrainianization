"""Локальні налаштування ШІ: `data/local/settings.json` (gitignored). Ключі API — лише тут або в змінних середовища.

  {"ai_consent": true,                         // «це мій власний голос» — до першої генерації
   "ai_license_accepted": {"fish-s2-pro": "2026-11-22"},
   "ai_engines": {"<двигун>": {"upload_consent": true, "api_key": "…", "model": "…"}},
   "ai": {"fish_model": "...", "fish_repo": "...", "fish_py": "..."}}
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # `python -I` не додає теку скрипта
from studio.paths import ROOT  # noqa: E402

CONSENT_TEXT = "Це мій власний голос: я клоную лише його і згоден(на), що ШІ-репліки позначаються «ШІ»"


class ConsentError(Exception):
    """Немає потрібної згоди користувача — генерацію не починаємо."""


def settings_path() -> Path:
    return Path(os.environ.get("WC3UA_ROOT") or ROOT) / "data/local/settings.json"


def load() -> dict:
    try:
        d = json.loads(settings_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def save(patch: dict) -> dict:
    """Зливає `patch` у settings.json (інші ключі, напр. game_root, лишаються)."""
    cur = load()
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(cur.get(k), dict):
            cur[k] = {**cur[k], **v}
        else:
            cur[k] = v
    p = settings_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(cur, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, p)
    return cur


# ---- згода «мій власний голос»
def has_consent() -> bool:
    return load().get("ai_consent") is True


def set_consent(value: bool) -> None:
    save({"ai_consent": bool(value)})


def require_consent() -> None:
    if not has_consent():
        raise ConsentError("потрібна згода «" + CONSENT_TEXT + "»: python tools/run.py ai-consent --accept")


# ---- налаштування двигунів (хмарні: ключ і згода на вивантаження власних дублів стороннім)
def engine_settings(name: str) -> dict:
    d = (load().get("ai_engines") or {}).get(name)
    return d if isinstance(d, dict) else {}


def set_engine(name: str, **patch) -> None:
    save({"ai_engines": {name: {**engine_settings(name), **patch}}})


def api_key(name: str, env_var: str) -> str | None:
    """Ключ: змінна середовища має пріоритет над settings.json. Ніколи не логуємо й не віддаємо в UI."""
    return os.environ.get(env_var) or engine_settings(name).get("api_key") or None


def upload_consent(name: str) -> bool:
    return engine_settings(name).get("upload_consent") is True


def license_accepted(name: str) -> bool:
    return bool((load().get("ai_license_accepted") or {}).get(name))


def accept_license(name: str, date: str) -> None:
    save({"ai_license_accepted": {name: date}})


# ---- шляхи Fish (env > settings > за замовчуванням у корені проєкту)
def fish_paths() -> dict:
    s = load().get("ai") or {}
    root = Path(os.environ.get("WC3UA_ROOT") or ROOT)
    venv = ".venv-fish/Scripts/python.exe" if sys.platform.startswith("win") else ".venv-fish/bin/python"
    return {"py": os.environ.get("WC3_FISH_PY") or s.get("fish_py") or str(root / venv),
            "repo": os.environ.get("WC3_FISH_REPO") or s.get("fish_repo") or str(root / "tools/fish-speech"),
            "model": os.environ.get("WC3_FISH_MODEL") or s.get("fish_model") or str(root / "models/fish-s2-pro")}
