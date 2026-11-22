"""Еквалайзер персонажа: профілі, призначення групі, перезапис обраних дублів."""
from __future__ import annotations

from .catalogs import _opt
from .registry import Ctx, route


@route("GET", "/api/eq")
def eq_get(c: Ctx):
    q = c.query
    return c.svc.eq_json(q["cid"], q["gid"])


@route("POST", "/api/eq/profile")
def eq_profile(c: Ctx):
    d = c.data
    return c.svc.eq_save(d["cid"], d["gid"], d["profile"], d.get("id"), d.get("assign", True))


@route("POST", "/api/eq/delete")
def eq_delete(c: Ctx):
    d = c.data
    return c.svc.eq_delete(d["cid"], d["gid"], d["id"])


@route("POST", "/api/eq/assign")
def eq_assign(c: Ctx):
    d = c.data
    return c.svc.eq_assign(d["cid"], d["gid"], d.get("profile_id"))


@route("POST", "/api/eq/reexport")
def eq_reexport(c: Ctx):
    d = c.data
    return c.svc.reexport_group(d["cid"], d["gid"], _opt(d, "trim"))
