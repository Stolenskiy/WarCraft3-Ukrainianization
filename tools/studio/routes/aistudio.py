"""ШІ-студія: маршрути /api/ai/* → фасад AiStudio (tools/aistudio/api.py). Деталі — docs/plans/ai-studio-ui.md.
Adopt/discard лишаються в catalogs.py. Черга стартує ліниво (перша постановка), події — опитування `events?after=`."""
from __future__ import annotations

import functools

from aistudio import config
from aistudio.api import AiStudio
from aistudio.engines import EngineError, get_engine
from aistudio.jobs import JobError
from aistudio.params import DEFAULT_ENGINE, ParamsError
from aistudio.setup import SetupError

from ..svc.util import StudioError
from .registry import Ctx, route

DOMAIN = (ParamsError, config.ConsentError, EngineError, JobError, SetupError)


def studio(svc) -> AiStudio:
    """Один AiStudio на Service (черга й фоновий потік); тести можуть підставити свій у `svc._aistudio`."""
    ai = getattr(svc, "_aistudio", None)
    if ai is None:
        ai = svc._aistudio = AiStudio(svc)
    return ai


def api(fn):
    """Доменні помилки ШІ → StudioError (400 для POST, 404 для GET); решта обробляється сервером як завжди."""
    @functools.wraps(fn)
    def wrapped(c: Ctx):
        try:
            return fn(c)
        except DOMAIN as ex:
            raise StudioError(str(ex)) from ex
    return wrapped


def _line(c: Ctx) -> tuple[str, str, str]:
    d = c.data
    return d["cid"], d["gid"], d["lid"]


@route("GET", "/api/ai/status")
@api
def ai_status(c: Ctx):
    return studio(c.svc).status(c.query.get("deep") == "1")


@route("GET", "/api/ai/engines")
@api
def ai_engines(c: Ctx):
    return studio(c.svc).engines()


@route("POST", "/api/ai/consent")
@api
def ai_consent(c: Ctx):
    return studio(c.svc).set_consent(bool(c.data.get("accept")))


@route("POST", "/api/ai/engine")
@api
def ai_engine(c: Ctx):
    d = c.data
    return studio(c.svc).set_engine(d["name"], upload_consent=d.get("upload_consent"), api_key=d.get("api_key"))


@route("GET", "/api/ai/refs")
@api
def ai_refs(c: Ctx):
    q = c.query
    return studio(c.svc).ref_candidates(q["cid"], q["gid"], q["lid"], q.get("approved") == "1")


@route("POST", "/api/ai/generate")
@api
def ai_generate(c: Ctx):
    ai = studio(c.svc)
    get_engine((c.data.get("params") or {}).get("engine") or DEFAULT_ENGINE).check_ready()   # не готовий/без згоди → 400 одразу, а не збій у черзі
    job = ai.submit(*_line(c), c.data.get("params"), auto_pick=c.data.get("auto_pick") is True)
    ai.queue.start()
    return job


@route("POST", "/api/ai/again")
@api
def ai_again(c: Ctx):
    ai = studio(c.svc)
    get_engine(ai.based_on(*_line(c), c.data["file"])["engine"]).check_ready()
    job = ai.again(*_line(c), c.data["file"])
    ai.queue.start()
    return job


@route("POST", "/api/ai/based-on")
@api
def ai_based_on(c: Ctx):
    return studio(c.svc).based_on(*_line(c), c.data["file"])


@route("GET", "/api/ai/jobs")
@api
def ai_jobs(c: Ctx):
    states = [s for s in c.query.get("state", "").split(",") if s]
    return studio(c.svc).jobs(states or None)


@route("GET", "/api/ai/job")
@api
def ai_job(c: Ctx):
    return studio(c.svc).job(c.query["id"])


@route("POST", "/api/ai/cancel")
@api
def ai_cancel(c: Ctx):
    return studio(c.svc).cancel(c.data["id"])


@route("GET", "/api/ai/events")
@api
def ai_events(c: Ctx):
    return studio(c.svc).events(int(c.query.get("after", 0)))


@route("GET", "/api/ai/draft")
@api
def ai_draft_plan(c: Ctx):
    q = c.query
    return studio(c.svc).draft_plan(q["cid"], q.get("gid") or None, q.get("engine") or None)


@route("POST", "/api/ai/draft")
@api
def ai_draft(c: Ctx):
    ai, d = studio(c.svc), c.data
    res = ai.draft(d["cid"], d.get("gid") or None, d.get("engine") or None, bool(d.get("approve")))
    if res["queued"]:
        ai.queue.start()
    return res


@route("POST", "/api/ai/draft/cancel")
@api
def ai_draft_cancel(c: Ctx):
    d = c.data
    return studio(c.svc).draft_cancel(d.get("cid"), d.get("gid"), d.get("batch"))
