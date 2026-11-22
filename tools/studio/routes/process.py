"""Обробка для гри: ручне обрізання, темп, налаштування, «Як у грі»."""
from __future__ import annotations

from .catalogs import _opt
from .registry import Ctx, File, route


@route("POST", "/api/trim")
def trim(c: Ctx):
    d = c.data
    return c.svc.set_trim(d["cid"], d["gid"], d["lid"], d["file"], d.get("start"), d.get("end"), _opt(d, "auto_trim"))


@route("POST", "/api/tempo")
def tempo(c: Ctx):
    d = c.data
    return c.svc.set_tempo(d["cid"], d["gid"], d["lid"], d["file"], d.get("tempo"))


@route("GET", "/api/settings")
def settings_get(c: Ctx):
    return c.svc.get_settings()


@route("POST", "/api/settings")
def settings_set(c: Ctx):
    return c.svc.set_settings(c.data)


@route("GET", "/api/preview")
def preview(c: Ctx):
    q = c.query
    return File(c.svc.preview(q["cid"], q["gid"], q["lid"], q["file"]), "audio/wav")
