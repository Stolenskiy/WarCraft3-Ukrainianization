"""Пресет персонажа на юніт: стан і пропозиція з voice bible, збереження, «голос персонажа» дубля для A/B."""
from __future__ import annotations

from .registry import Ctx, File, route


@route("GET", "/api/character")
def character_get(c: Ctx):
    q = c.query
    return c.svc.character_json(q["cid"], q["gid"])


@route("POST", "/api/character")
def character_set(c: Ctx):
    d = c.data
    return c.svc.character_set(d["cid"], d["gid"], d.get("preset"))


@route("GET", "/api/character/audio")
def character_audio(c: Ctx):
    q = c.query
    return File(c.svc.character_audio(q["cid"], q["gid"], q["lid"], q["file"]), "audio/wav")
