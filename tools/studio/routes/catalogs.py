"""Каталоги, групи, аудіо та дії над репліками (дублі, оригінал, текст)."""
from __future__ import annotations

from . import voices  # noqa: F401  (реєструє /audio/voice/… раніше за загальний /audio/…)
from .registry import Ctx, File, route


def _opt(d: dict, key: str) -> bool | None:
    """Застарілий явний параметр запиту (trim/auto_trim); немає → береться з налаштувань."""
    return None if d.get(key) is None else bool(d[key])


@route("GET", "/api/catalogs")
def catalogs(c: Ctx):
    return c.svc.catalogs_json()


@route("GET", "/api/group/<cid>/<gid>")
def group(c: Ctx):
    return c.svc.group_json(c.params["cid"], c.params["gid"])


@route("GET", "/audio/<kind>/<cid>/<gid>/<name>")
def audio(c: Ctx):
    p = c.params
    return File(c.svc.audio_path(p["kind"], p["cid"], p["gid"], p["name"]), "audio/wav")


@route("POST", "/api/take")
def take(c: Ctx):
    q = c.query
    return c.svc.add_take(q["cid"], q["gid"], q["lid"], c.body)


@route("POST", "/api/approve")
def approve(c: Ctx):
    d = c.data
    return c.svc.approve(d["cid"], d["gid"], d["lid"], d["file"], _opt(d, "trim"))


@route("POST", "/api/unapprove")
def unapprove(c: Ctx):
    d = c.data
    return c.svc.unapprove(d["cid"], d["gid"], d["lid"])


@route("POST", "/api/original")
def original(c: Ctx):
    d = c.data
    return c.svc.keep_original(d["cid"], d["gid"], d["lid"], d["lang"])


@route("POST", "/api/original/clear")
def original_clear(c: Ctx):
    d = c.data
    return c.svc.clear_original(d["cid"], d["gid"], d["lid"])


@route("POST", "/api/delete")
def delete(c: Ctx):
    d = c.data
    return c.svc.delete(d["cid"], d["gid"], d["lid"], d["file"])


@route("POST", "/api/restore")
def restore(c: Ctx):
    d = c.data
    return c.svc.restore(d["cid"], d["gid"], d["lid"], d["file"])


@route("POST", "/api/text")
def text(c: Ctx):
    d = c.data
    return c.svc.set_text(d["cid"], d["gid"], d["lid"], d.get("text", ""))


@route("POST", "/api/ai/adopt")
def ai_adopt(c: Ctx):
    d = c.data
    return c.svc.adopt_ai(d["cid"], d["gid"], d["lid"], d["file"], fit=bool(d.get("fit")))


@route("POST", "/api/ai/auto-pick")
def ai_auto_pick(c: Ctx):
    d = c.data
    return c.svc.auto_pick_ai(d["cid"], d["gid"], d["lid"], among=d.get("among"), fit=d.get("fit", True) is not False)


@route("POST", "/api/ai/discard")
def ai_discard(c: Ctx):
    d = c.data
    return c.svc.discard_ai(d["cid"], d["gid"], d["lid"], d["file"])
