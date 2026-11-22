"""Тека гри (tools/gameconf.py): поточний шлях і його джерело, збереження, автопошук. Нічого в гру не пише."""
from __future__ import annotations

import gameconf
import install_voices

from ..svc.util import StudioError
from .registry import Ctx, route


def _state() -> dict:
    install_voices.GAME = gameconf.get_game_root()      # плани й встановлення бачать нову теку без перезапуску студії
    return {**gameconf.describe(), "candidates": gameconf.detect()}


@route("GET", "/api/game-root")
def game_root_get(c: Ctx):
    return _state()


@route("POST", "/api/game-root")
def game_root_set(c: Ctx):
    d = c.data
    if gameconf.describe()["env_overrides"]:
        raise StudioError(f"тека задана змінною {gameconf.ENV} — змініть її там (налаштування студії їй поступаються)")
    try:
        if d.get("clear"):
            gameconf.clear_game_root()
        elif d.get("autodetect"):
            found = gameconf.detect()
            if not found:
                raise StudioError("гру не знайдено автоматично — вкажіть теку вручну")
            gameconf.set_game_root(found[0])
        else:
            gameconf.set_game_root(d["path"])
    except ValueError as ex:
        raise StudioError(str(ex)) from ex
    return _state()
