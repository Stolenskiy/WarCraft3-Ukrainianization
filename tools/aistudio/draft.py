"""ШІ-чернетка юніта / раси одним кліком: ШІ-заглушки для реплік, де ще немає НІ власного дубля, НІ ШІ-варіанта.

Кожна така репліка = окреме завдання черги (`JobQueue`, n = 1, поточний двигун) з позначкою `draft = {batch, approve}` —
оцінка часу, прогрес і скасування ті самі, що й у звичайної генерації. Референси — лише ВЛАСНІ обрані дублі:
автовибір групи (як у звичайній генерації), а якщо в юніта своїх обраних ще немає — найдовші обрані дублі тієї ж раси
(той самий голос користувача). Пропускаються: свідомо залишений оригінал, репліки без слів / без тексту, ті, що вже в черзі.

`approve`: після готовності ШІ-варіант береться в дублі й ОБИРАЄТЬСЯ для гри, але лише якщо в репліці досі нічого не
обрано й немає жодного власного запису — живий запис завжди має пріоритет. Результат лишається позначеним «ШІ».
"""
from __future__ import annotations

import secrets
import time

from studio import ai, aigen

from . import config, refs
from .params import DEFAULT_ENGINE, GenParams

ACTIVE = ("queued", "running")


class Drafts:
    def __init__(self, svc, queue) -> None:
        self.svc, self.queue = svc, queue
        queue.listeners.append(self._on_event)

    # ------------------------------------------------------------ що чернетити
    def _scope(self, cid: str, gid: str | None) -> list:
        groups = self.svc.groups(cid)
        if gid is None:
            return groups
        self.svc.lines(cid, gid)                                  # невідома група → StudioError
        return [g for g in groups if g.id == gid]

    def _busy(self) -> set[tuple[str, str, str]]:
        with self.queue.cv:
            return {(r["cid"], r["gid"], r["lid"]) for r in self.queue.jobs.values() if r["state"] in ACTIVE}

    def todo(self, cid: str, gid: str, busy: set | None = None) -> list[str]:
        """Репліки групи без власного дубля й без ШІ (варіанта чи ШІ-дубля), не в черзі, з текстом і словами."""
        busy = self._busy() if busy is None else busy
        with self.svc.lock:
            stems, st = ai.ai_stems(cid, gid), self.svc.store(cid).data["groups"].get(gid, {})
            out = []
            for ln in self.svc.lines(cid, gid):
                e = st.get(ln.id)
                text = (e or {}).get("ua_text")
                text = (text if text is not None else ln.ua_hint or "").strip()
                if ln.no_speech or not text or (cid, gid, ln.id) in busy:
                    continue
                if ai.voice_kind(e, ln.stem in stems) == "orig":
                    out.append(ln.id)
            return out

    def _own_refs(self, cid: str) -> list[dict]:
        """Обрані власні дублі раси (refs.list_ref_candidates: без ШІ, видалених і reference*/), найдовші спершу."""
        with self.svc.lock:
            cands = refs.list_ref_candidates(self.svc, cid, approved_only=True)
        return sorted(cands, key=lambda c: -c["dur"])

    def plan(self, cid: str, gid: str | None = None, engine: str | None = None) -> dict:
        """Що буде поставлено в чергу (нічого не запускає): групи з репліками й прогресом, оцінка часу на репліку і черги попереду."""
        eng = self.queue.engine_factory(engine or DEFAULT_ENGINE)
        busy, own = self._busy(), self._own_refs(cid)
        groups = [{"gid": g.id, "title": g.title, "todo": self.todo(cid, g.id, busy), "mix": self.svc.voice_mix(cid, g.id)}
                  for g in self._scope(cid, gid)]
        e = self.queue.timing.est(eng.info.name)
        act = self.queue.list(ACTIVE)                             # з оцінкою eta для всієї черги
        return {"cid": cid, "gid": gid, "engine": eng.info.name, "license": eng.info.output_license, "groups": groups,
                "todo": sum(len(g["todo"]) for g in groups), "refs": len(own), "consent": config.has_consent(),
                "per_line": round(e["load"] + e["per"] + e["metrics"]), "ahead": max((r["eta"]["left"] for r in act), default=0),
                "active": sum(1 for r in act if r.get("draft") and r["cid"] == cid and (gid is None or r["gid"] == gid))}

    # ------------------------------------------------------------ у чергу / скасувати
    def submit(self, cid: str, gid: str | None = None, engine: str | None = None, approve: bool = False) -> dict:
        config.require_consent()
        eng = self.queue.engine_factory(engine or DEFAULT_ENGINE)
        eng.check_ready()
        scope, busy = self._scope(cid, gid), self._busy()
        work = [(g.id, lids) for g in scope if (lids := self.todo(cid, g.id, busy))]
        if not work:
            return {"batch": None, "queued": 0, "jobs": [], "skipped": []}
        own = self._own_refs(cid)
        if not own:
            raise refs.RefError("спершу запишіть і оберіть для гри хоча б один власний дубль цієї раси — ШІ клонує лише ваш голос")
        fallback = tuple(c["key"] for c in own[:aigen.MAX_REFS])
        can_pick = "ref_takes" in eng.info.supports
        batch, jobs, skipped = f"draft-{int(time.time())}-{secrets.token_hex(2)}", [], []
        for g, lids in work:
            mine = any(c["gid"] == g for c in own)                # у групі є свої обрані — автовибір, як у звичайній генерації
            if not mine and not can_pick:
                skipped += [{"gid": g, "lid": lid, "reason": "у юніта немає обраних власних дублів, а двигун не дає обрати референси"}
                            for lid in lids]
                continue
            p = GenParams(n=1, engine=eng.info.name, ref_takes=None if mine else fallback)
            for lid in lids:
                jobs.append(self.queue.submit(cid, g, lid, p, draft={"batch": batch, "approve": bool(approve)})["id"])
        return {"batch": batch if jobs else None, "queued": len(jobs), "jobs": jobs, "skipped": skipped,
                "license": eng.info.output_license}

    def cancel(self, cid: str | None = None, gid: str | None = None, batch: str | None = None) -> dict:
        """Скасувати активні завдання чернетки (усі, раси, юніта або одного пакета)."""
        with self.queue.cv:
            ids = [r["id"] for r in self.queue._ordered() if r["state"] in ACTIVE and r.get("draft")
                   and (cid is None or r["cid"] == cid) and (gid is None or r["gid"] == gid)
                   and (batch is None or r["draft"].get("batch") == batch)]
        for jid in reversed(ids):                                 # спершу хвіст черги — робітник не встигне взяти наступне
            self.queue.cancel(jid)
        return {"cancelled": len(ids)}

    # ------------------------------------------------------------ «одразу обрати як чернетку»
    def _on_event(self, ev: dict) -> None:
        if ev.get("type") != "state" or ev.get("state") != "done":
            return
        rec = self.queue.get(ev["job"])
        if (rec.get("draft") or {}).get("approve") and rec["results"]:
            self.adopt_draft(rec["cid"], rec["gid"], rec["lid"], rec["results"][0]["file"])

    def adopt_draft(self, cid: str, gid: str, lid: str, file: str) -> bool:
        """Взяти ШІ-варіант у дублі й обрати для гри — лише якщо досі нічого не обрано й немає власного запису."""
        with self.svc.lock:
            ln = self.svc.line(cid, gid, lid)
            e = self.svc.store(cid).entry(gid, lid)
            if e["approved"] or e["original"] or any(not t.get("deleted") and t.get("source") != "ai" for t in e["takes"]):
                return False
            res = self.svc.adopt_ai(cid, gid, lid, file)
            take = next(t["file"] for t in reversed(res["takes"]) if t["source"] == "ai")
            self.svc.approve(cid, gid, lid, take)
            self.svc.store(cid).log(gid, lid, f"ШІ-чернетка {file} обрана для гри (власний запис її замінить)")
            self.svc._done(cid, gid, ln)
            return True
