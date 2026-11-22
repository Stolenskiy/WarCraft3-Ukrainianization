"""ШІ-очищення дублів: /api/enhance/* → EnhanceQueue (tools/aistudio/enhance_jobs.py). Одна черга на Service."""
from __future__ import annotations

import functools

from aistudio import enhance, eta
from aistudio.enhance_jobs import EnhanceJobError, EnhanceQueue

from .. import paths
from ..svc.util import StudioError
from .registry import Ctx, route


def queue(svc) -> EnhanceQueue:
    """Одна черга на Service; тести можуть підставити свою в `svc._enhance`."""
    q = getattr(svc, "_enhance", None)
    if q is None:
        q = svc._enhance = EnhanceQueue(svc, eta.Timing(paths.STATE_DIR / "enhance-timing.json"))
    return q


def api(fn):
    @functools.wraps(fn)
    def wrapped(c: Ctx):
        try:
            return fn(c)
        except (EnhanceJobError, enhance.EnhanceError) as ex:
            raise StudioError(str(ex)) from ex
    return wrapped


@route("GET", "/api/enhance/status")
def enhance_status(c: Ctx):
    return {**enhance.status(), "jobs": queue(c.svc).list()}


@route("GET", "/api/enhance/jobs")
def enhance_jobs(c: Ctx):
    return queue(c.svc).list()


@route("POST", "/api/enhance")
@api
def enhance_submit(c: Ctx):
    return queue(c.svc).submit(c.data.get("items"), approve=bool(c.data.get("approve")))


@route("POST", "/api/enhance/setup")
@api
def enhance_setup(c: Ctx):
    return queue(c.svc).submit_setup()


@route("POST", "/api/enhance/cancel")
@api
def enhance_cancel(c: Ctx):
    return queue(c.svc).cancel(str(c.data.get("id") or ""))
