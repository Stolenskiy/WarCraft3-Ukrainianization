"""Фасад для маршрутів студії (UI-фаза): усе — словники/списки, готові до JSON. Деталі проводки — docs/plans/ai-studio-ui.md."""
from __future__ import annotations

from . import config, refs, setup
from .engines import get_engine, list_engines
from .jobs import JobQueue
from .params import GenParams, schema


class AiStudio:
    def __init__(self, svc, queue: JobQueue | None = None) -> None:
        self.svc = svc
        self.queue = queue or JobQueue(svc)

    # ---- стан і налаштування
    def status(self, deep: bool = False) -> dict:
        """GET /api/ai/status → готовність Fish + згода + schema параметрів + двигуни."""
        return {**setup.status(deep), "schema": schema(), "engines": list_engines(), "consent_text": config.CONSENT_TEXT}

    def engines(self) -> list[dict]:
        return list_engines()

    def set_consent(self, accept: bool) -> dict:
        config.set_consent(accept)
        return {"ai_consent": config.has_consent()}

    def set_engine(self, name: str, *, upload_consent: bool | None = None, api_key: str | None = None) -> dict:
        """Налаштування двигуна: згода на вивантаження власних дублів, ключ API (ключ назад НЕ віддається)."""
        eng = get_engine(name)
        patch = {}
        if upload_consent is not None:
            patch["upload_consent"] = bool(upload_consent)
        if api_key is not None:
            patch["api_key"] = api_key
        if patch:
            config.set_engine(eng.info.name, **patch)
        return next(e for e in list_engines() if e["name"] == name)

    # ---- референси
    def ref_candidates(self, cid: str, gid: str, lid: str, approved_only: bool = False) -> list[dict]:
        return [refs.public(c) for c in refs.list_ref_candidates(self.svc, cid, gid, lid, approved_only)]

    # ---- генерація
    def submit(self, cid: str, gid: str, lid: str, params: dict | None, auto_pick: bool = False) -> dict:
        return self.queue.submit(cid, gid, lid, GenParams.from_dict(params), auto_pick=auto_pick)

    def again(self, cid: str, gid: str, lid: str, file: str) -> dict:
        return self.queue.again(cid, gid, lid, file)

    def based_on(self, cid: str, gid: str, lid: str, file: str) -> dict:
        from pathlib import Path
        return self.queue.based_on(cid, gid, Path(lid).stem, file)

    def jobs(self, states=None) -> list[dict]:
        return self.queue.list(states)

    def job(self, jid: str) -> dict:
        return self.queue.get(jid)

    def cancel(self, jid: str) -> dict:
        return self.queue.cancel(jid)

    def events(self, after: int = 0) -> list[dict]:
        return self.queue.events(after)
