"""Реєстр маршрутів: `@route("POST", "/api/trim")` у модулі фічі; server.py лише диспетчеризує.

Шаблон — сегменти через «/»: літерал, `<ім'я>` (один сегмент) або `<ім'я:path>` (решта шляху, ≥ 1 сегмент).
Обробник отримує `Ctx` і повертає dict/list (JSON) або `File` (файл з диска). Перший збіг у порядку реєстрації
виграє, тому конкретніші шаблони реєструються раніше. Помилки (StudioError, InstallError, OSError, KeyError…)
перетворює server.py — обробники їх просто кидають.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


@dataclass
class File:
    path: Path
    ctype: str | None = None


@dataclass
class Ctx:
    svc: Any
    path: str = ""
    params: dict[str, str] = field(default_factory=dict)
    body: bytes = b""

    @property
    def query(self) -> dict[str, str]:
        return {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}

    @property
    def data(self) -> dict:
        """JSON-тіло POST (порожнє тіло → {}); некоректний JSON → ValueError → 400."""
        return json.loads(self.body or b"{}")


Handler = Callable[[Ctx], Any]
ROUTES: dict[str, list[tuple[str, list[str], Handler]]] = {"GET": [], "POST": []}


def route(method: str, template: str) -> Callable[[Handler], Handler]:
    def deco(fn: Handler) -> Handler:
        ROUTES[method].append((template, [s for s in template.strip("/").split("/") if s], fn))
        return fn
    return deco


def _try(segs: list[str], parts: list[str]) -> dict[str, str] | None:
    params: dict[str, str] = {}
    for i, s in enumerate(segs):
        if s.endswith(":path>"):
            if len(parts) <= i:
                return None
            params[s[1:-6]] = "/".join(parts[i:])
            return params
        if i >= len(parts):
            return None
        if s.startswith("<"):
            params[s[1:-1]] = parts[i]
        elif s != parts[i]:
            return None
    return params if len(parts) == len(segs) else None


def match(method: str, parts: list[str]) -> tuple[Handler, dict[str, str]] | None:
    for _, segs, fn in ROUTES.get(method, []):
        params = _try(segs, parts)
        if params is not None:
            return fn, params
    return None
