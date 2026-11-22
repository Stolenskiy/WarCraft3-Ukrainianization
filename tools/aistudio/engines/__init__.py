"""Реєстр двигунів: автопошук `engines/*.py` (кожен файл може оголосити класи-нащадки Engine).

`list_engines()` — для UI-вибору (метадані + status()); `get_engine(name)` — екземпляр; `output_license(name)` — ліцензія
ШІ-реплік двигуна (невідомий двигун → CC BY-NC 4.0). Додати двигун: docs/runbooks/add-ai-engine.md.
Файли, що не імпортуються, пропускаються з поміткою в `load_errors()` (зламаний плагін не валить студію).
"""
from __future__ import annotations

import importlib
import inspect
import pkgutil
from pathlib import Path

from .base import NC_LICENSE, Cancelled, Engine, EngineError, EngineInfo  # noqa: F401

_SKIP = {"base", "procrun"}
_extra: dict[str, type[Engine]] = {}      # реєстрація зсередини коду/тестів
_errors: dict[str, str] = {}


def register(cls: type[Engine]) -> type[Engine]:
    _extra[cls.info.name] = cls
    return cls


def unregister(name: str) -> None:
    _extra.pop(name, None)


def discover() -> dict[str, type[Engine]]:
    found: dict[str, type[Engine]] = {}
    _errors.clear()
    for m in pkgutil.iter_modules([str(Path(__file__).parent)]):
        if m.name in _SKIP or m.name.startswith("_"):
            continue
        try:
            mod = importlib.import_module(f"{__name__}.{m.name}")
        except Exception as ex:      # noqa: BLE001 — зламаний плагін не повинен валити студію
            _errors[m.name] = f"{type(ex).__name__}: {ex}"
            continue
        for _, cls in inspect.getmembers(mod, inspect.isclass):
            if issubclass(cls, Engine) and cls is not Engine and cls.__module__ == mod.__name__ and hasattr(cls, "info"):
                found[cls.info.name] = cls
    found.update(_extra)
    return found


def load_errors() -> dict[str, str]:
    return dict(_errors)


def get_engine(name: str) -> Engine:
    cls = discover().get(name)
    if cls is None:
        raise EngineError(f"невідомий двигун {name!r}; доступні: {', '.join(sorted(discover()))}")
    return cls()


def list_engines() -> list[dict]:
    """[{...EngineInfo, status: {state, detail}, warnings: [...], upload_consent: bool|None}] — для вибору двигуна в UI."""
    from .. import config
    out = []
    for name, cls in sorted(discover().items()):
        e = cls()
        try:
            st = e.status()
        except Exception as ex:      # noqa: BLE001
            st = {"state": "missing_env", "detail": f"status() впав: {ex}"}
        out.append({**e.info.to_dict(), "status": st, "warnings": e.warnings(),
                    "upload_consent": config.upload_consent(name) if e.info.cloud else None})
    return out


def output_license(name: str | None) -> str:
    """Ліцензія ШІ-реплік двигуна для пакетів; невідомий/відсутній → CC BY-NC 4.0."""
    try:
        return discover()[name].info.output_license
    except (KeyError, AttributeError, TypeError):
        return NC_LICENSE
