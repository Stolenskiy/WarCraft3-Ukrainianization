"""Сторінка студії та статичні файли: / і /static/{js,css}/<файл> (лише .js/.css із web/js і web/css)."""
from __future__ import annotations

from pathlib import Path

from .registry import Ctx, File, route

WEB = Path(__file__).resolve().parent.parent / "web"
STATIC = {"js": ".js", "css": ".css"}


@route("GET", "/")
def index(c: Ctx):
    return File(WEB / "index.html")


@route("GET", "/static/<kind>/<name>")
def static(c: Ctx):
    ext = STATIC.get(c.params["kind"])
    name = c.params["name"]
    p = (WEB / c.params["kind"] / name).resolve()
    if not ext or p.suffix != ext or p.parent != (WEB / c.params["kind"]).resolve():   # без виходу з web/js, web/css
        return File(WEB / "__none__")
    return File(p)
