"""Черга ШІ-очищення дублів: завдання по черзі у фоновому потоці, прогрес і оцінка часу, скасування.

Завдання «clean»: список дублів {cid, gid, lid, file} → для кожного НОВИЙ дубль (`source: "enhanced"`, `enhanced_from`);
оригінал не змінюється. `approve`: якщо очищали обраний для гри дубль — обрати очищений замість нього.
Завдання «setup»: встановлення .venv-enhance і ваг (enhance.setup) — кнопкою з браузера.
Стан — у пам’яті (завдання короткі: секунди на дубль); після перезапуску студії черга порожня.
"""
from __future__ import annotations

import secrets
import tempfile
import threading
import time
from pathlib import Path

from studio.svc.util import StudioError

from . import enhance, eta
from .engines.procrun import WorkerRunner

KEEP_FINISHED = 20


class EnhanceJobError(Exception):
    pass


class EnhanceQueue:
    def __init__(self, svc, timing: eta.Timing, runner_factory=WorkerRunner, setup_fn=None) -> None:
        self.svc, self.timing = svc, timing
        self.runner_factory, self.setup_fn = runner_factory, setup_fn or enhance.setup
        self.cv = threading.Condition()
        self.jobs: list[dict] = []
        self._runner: WorkerRunner | None = None
        self._cancel: set[str] = set()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------ API
    def submit(self, items: list[dict], approve: bool = False) -> dict:
        if not isinstance(items, list) or not items:
            raise EnhanceJobError("не обрано жодного дубля")
        clean = []
        for it in items:
            if not isinstance(it, dict) or not all(isinstance(it.get(k), str) and it.get(k) for k in ("cid", "gid", "lid", "file")):
                raise EnhanceJobError("кожен дубль: {cid, gid, lid, file}")
            self.svc.take_of(it["cid"], it["gid"], it["lid"], it["file"])        # існує? (StudioError інакше)
            clean.append({k: it[k] for k in ("cid", "gid", "lid", "file")})
        st = enhance.status()
        if st["state"] != "ready":
            raise EnhanceJobError(f"ШІ-очищення не встановлено ({st['detail']}) — натисніть «Встановити»")
        return self._add({"kind": "clean", "items": clean, "approve": bool(approve), "total": len(clean)})

    def submit_setup(self) -> dict:
        with self.cv:
            if any(j["kind"] == "setup" and j["state"] in ("queued", "running") for j in self.jobs):
                raise EnhanceJobError("встановлення вже йде")
        return self._add({"kind": "setup", "items": [], "approve": False, "total": 1})

    def cancel(self, jid: str) -> dict:
        with self.cv:
            j = self._get(jid)
            if j["state"] == "queued":
                j.update(state="cancelled", finished=time.time())
            elif j["state"] == "running":
                self._cancel.add(jid)
                if self._runner is not None:
                    self._runner.cancel()
            return dict(j)

    def list(self) -> list[dict]:
        with self.cv:
            out = [{k: v for k, v in j.items() if k != "items"} | {"keys": sorted({f"{i['cid']}/{i['gid']}/{i['lid']}" for i in j["items"]})} for j in self.jobs]
        t, ahead = time.time(), 0.0
        for j in out:
            if j["state"] in ("queued", "running"):
                left = self._left(j, t)
                j["eta"] = {"left": round(ahead + left), "total": round(self._total(j)), "ahead": round(ahead)}
                ahead += left
        return out

    # ------------------------------------------------------------ виконання
    def _add(self, spec: dict) -> dict:
        with self.cv:
            j = {"id": f"e{int(time.time())}-{secrets.token_hex(3)}", "state": "queued", "phase": "queued", "done": 0, "failed": 0,
                 "results": [], "error": None, "created": time.time(), "t": time.time(), "finished": None, **spec}
            self.jobs.append(j)
            done = [x for x in self.jobs if x["state"] not in ("queued", "running")]
            for x in done[:-KEEP_FINISHED]:
                self.jobs.remove(x)
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._loop, daemon=True)
                self._thread.start()
            self.cv.notify_all()
            return {k: v for k, v in j.items() if k != "items"}

    def _get(self, jid: str) -> dict:
        for j in self.jobs:
            if j["id"] == jid:
                return j
        raise EnhanceJobError(f"невідоме завдання {jid}")

    def _set(self, j: dict, **kw) -> None:
        with self.cv:
            j.update(kw, t=time.time())

    def _loop(self) -> None:
        while True:
            with self.cv:
                j = next((x for x in self.jobs if x["state"] == "queued"), None)
                if j is None:
                    self._thread = None
                    return
                j.update(state="running", started=time.time(), t=time.time())
            try:
                (self._setup if j["kind"] == "setup" else self._clean)(j)
            except Exception as ex:  # noqa: BLE001 — збій одного завдання не зупиняє чергу
                self._set(j, state="failed", error=str(ex) or type(ex).__name__, finished=time.time())
            else:
                self._set(j, state="cancelled" if j["id"] in self._cancel else "done", phase="done", finished=time.time())

    def _setup(self, j: dict) -> None:
        self._set(j, phase="setup")
        self.setup_fn(say=lambda msg: self._set(j, message=msg))
        self._set(j, done=1)

    def _clean(self, j: dict) -> None:
        self._set(j, phase="loading")
        p = enhance.paths()
        with tempfile.TemporaryDirectory(prefix="wc3ua-enhance-") as td:
            tmp = Path(td)
            work = [{"in": str(self.svc.take_file(it["cid"], it["gid"], it["lid"], it["file"])), "out": str(tmp / f"{i}.wav"), **it}
                    for i, it in enumerate(j["items"])]
            by_out = {w["out"]: w for w in work}
            runner = self.runner_factory()
            with self.cv:
                self._runner = runner

            def on_msg(m: dict) -> None:
                if "loaded" in m:
                    self.timing.learn(enhance.ENGINE, "load", m["loaded"])
                    self._set(j, phase="enhancing")
                    return
                w = by_out.get(m.get("out"))
                if w is None:
                    return
                res = {"lid": w["lid"], "file": w["file"]}
                try:
                    if m.get("error"):
                        raise EnhanceJobError(m["error"])
                    self.timing.learn(enhance.ENGINE, "per", m.get("sec"))
                    res.update(self.svc.add_enhanced_take(w["cid"], w["gid"], w["lid"], w["file"], Path(w["out"]),
                                                          engine=enhance.ENGINE, approve=j["approve"]))
                except (EnhanceJobError, StudioError, enhance.EnhanceError) as ex:
                    res["error"] = str(ex)
                with self.cv:
                    j["results"].append(res)
                    j["failed"] += "error" in res
                self._set(j, done=j["done"] + 1, phase="enhancing")

            try:
                runner.run(str(p["py"]), str(enhance.WORKER), {"model": str(p["model"]), "jobs": [{"in": w["in"], "out": w["out"]} for w in work]}, on_msg)
            except Exception:
                if j["id"] in self._cancel:
                    return
                raise
            finally:
                with self.cv:
                    self._runner = None

    # ------------------------------------------------------------ оцінка часу
    def _est(self) -> dict:
        return self.timing.est(enhance.ENGINE, enhance.TIMING_DEFAULTS)

    def _total(self, j: dict) -> float:
        return 60.0 if j["kind"] == "setup" else self._est()["load"] + j["total"] * self._est()["per"]

    def _left(self, j: dict, t: float) -> float:
        if j["kind"] == "setup":
            return max(5.0, 60.0 - (t - j.get("started", t))) if j["state"] == "running" else 60.0
        e, since = self._est(), t - j.get("t", t)
        if j["state"] == "queued":
            return self._total(j)
        rest = j["total"] - j["done"]
        if j["phase"] == "loading":
            return max(0.5, e["load"] - since) + rest * e["per"]
        return max(0.2, e["per"] - since) + max(0, rest - 1) * e["per"] if rest else 0.0
