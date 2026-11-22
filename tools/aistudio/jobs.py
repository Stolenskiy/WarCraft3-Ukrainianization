"""Черга ШІ-генерації: один GPU/MPS-робітник за раз, FIFO, стани, події, скасування (з убивством підпроцесу), перезапуск.

Завдання = одна репліка × параметри (GenParams, n варіантів). Файли `<audio/ai>/.jobs/<id>.json` (gitignored) переживають
перезапуск студії: `queued` лишаються в черзі, перерване `running` повертається в чергу (до MAX_ATTEMPTS спроб).
Чистий Python: студія викликає `JobQueue` з маршрутів, `run_next()` — синхронно (CLI/тести), `start()` — фоновий потік.
Жоден процес не запускає двох робітників одночасно: `gpu.lock` із pid (живий власник → «зайнято»).
"""
from __future__ import annotations

import json
import os
import secrets
import tempfile
import threading
import time
from collections import deque
from dataclasses import replace
from pathlib import Path

from studio import ai, aigen
from studio.catalog import duration
from studio.core import now

from . import config, eta, refs
from .engines import Cancelled, EngineError, get_engine
from .params import SEED_MAX, GenParams, ParamsError

STATES = ("queued", "running", "done", "failed", "cancelled")
TERMINAL = ("done", "failed", "cancelled")
MAX_ATTEMPTS = 3
KEEP_TERMINAL = 60
RETRIES = 1


def pid_alive(pid: int) -> bool:
    if pid == os.getpid():
        return True
    if os.name == "nt":                                   # pragma: no cover — os.kill(pid, 0) на Windows небезпечний
        import ctypes
        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if h:
            ctypes.windll.kernel32.CloseHandle(h)
        return bool(h)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class JobError(Exception):
    pass


class NullAsr:
    """Без Whisper (немає mlx_whisper): CER лишається null — це не помилка."""

    def transcribe(self, paths):
        return {}


def default_asr():
    try:
        import mlx_whisper  # noqa: F401
    except ImportError:
        return NullAsr()
    return aigen.WhisperCer()


class JobQueue:
    def __init__(self, svc, jobs_dir: Path | None = None, *, engine_factory=get_engine, asr_factory=default_asr) -> None:
        self.svc = svc
        self.dir = Path(jobs_dir or ai.AI_ROOT / ".jobs")
        self.dir.mkdir(parents=True, exist_ok=True)
        self.engine_factory, self.asr_factory = engine_factory, asr_factory
        self.cv = threading.Condition()
        self.jobs: dict[str, dict] = {}
        self._events: deque = deque(maxlen=500)
        self._eid = 0
        self._engine = None
        self._current: str | None = None
        self._cancel: set[str] = set()
        self._thread: threading.Thread | None = None
        self._stop = False
        self.listeners: list = []
        self.timing = eta.Timing(self.dir / "timing.json")
        self._load()

    # ------------------------------------------------------------ збереження
    def _path(self, jid: str) -> Path:
        return self.dir / f"{jid}.json"

    def _save(self, rec: dict) -> None:
        tmp = self._path(rec["id"]).with_suffix(".tmp")
        tmp.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self._path(rec["id"]))

    def _load(self) -> None:
        for p in sorted(self.dir.glob("*.json")):
            try:
                rec = json.loads(p.read_text(encoding="utf-8"))
                assert isinstance(rec, dict) and rec["state"] in STATES and rec["id"] == p.stem
            except (OSError, ValueError, KeyError, AssertionError):
                continue
            self.jobs[rec["id"]] = rec
        for rec in self._ordered():
            if rec["state"] == "running":                       # студія впала посеред завдання
                rec["attempts"] = rec.get("attempts", 0) + 1
                if rec["attempts"] >= MAX_ATTEMPTS:
                    rec.update(state="failed", error="перервано перезапуском студії забагато разів", finished=now())
                else:
                    rec.update(state="queued", started=None, progress={"done": 0, "total": rec["params"]["n"], "phase": "queued"})
                self._save(rec)
        done = [r for r in self._ordered() if r["state"] in TERMINAL]
        for rec in done[:-KEEP_TERMINAL]:
            self._path(rec["id"]).unlink(missing_ok=True)
            del self.jobs[rec["id"]]

    def _ordered(self) -> list[dict]:
        return sorted(self.jobs.values(), key=lambda r: r["seq"])

    # ------------------------------------------------------------ події
    def _emit(self, rec: dict, typ: str, **kw) -> None:
        with self.cv:
            self._eid += 1
            ev = {"id": self._eid, "ts": now(), "job": rec["id"], "type": typ, "state": rec["state"], **kw}
            self._events.append(ev)
        for fn in list(self.listeners):
            try:
                fn(ev)
            except Exception:      # noqa: BLE001 — слухач не має ламати чергу
                pass

    def events(self, after: int = 0) -> list[dict]:
        """Події з id > after (опитування або SSE): type = state | progress | log."""
        with self.cv:
            return [e for e in self._events if e["id"] > after]

    def _set(self, rec: dict, **kw) -> None:
        with self.cv:
            rec.update(kw)
            self._save(rec)
        self._emit(rec, "state")

    # ------------------------------------------------------------ публічне API
    def submit(self, cid: str, gid: str, lid: str, params, *, parent: str | None = None) -> dict:
        p = params if isinstance(params, GenParams) else GenParams.from_dict(params)
        config.require_consent()
        eng = self.engine_factory(p.engine)
        self.svc.line(cid, gid, lid)                              # існує?
        if p.ref_takes is not None:
            refs.validate(self.svc, cid, gid, lid, p.ref_takes)    # ранній відмова: не після години в черзі
        _, unsupported = eng.map_params(p)
        warnings = [f"двигун {eng.info.name} не підтримує «{k}» — буде проігноровано" for k in unsupported] + eng.warnings()
        with self.cv:
            seq = max((r["seq"] for r in self.jobs.values()), default=0) + 1
            rec = {"id": f"{int(time.time())}-{secrets.token_hex(3)}", "seq": seq, "state": "queued", "cid": cid, "gid": gid, "lid": lid,
                   "params": p.to_dict(), "base_seed": p.seed if p.seed is not None else secrets.randbelow(SEED_MAX + 1),
                   "engine": eng.info.name, "license": eng.info.output_license, "parent": parent, "created": now(), "started": None,
                   "finished": None, "progress": {"done": 0, "total": p.n, "phase": "queued"}, "results": [], "error": None,
                   "warnings": warnings, "unsupported": unsupported, "attempts": 0}
            self.jobs[rec["id"]] = rec
            self._save(rec)
            self.cv.notify_all()
        self._emit(rec, "state")
        return dict(rec)

    def variant_params(self, cid: str, gid: str, stem: str, file: str) -> dict:
        wav = ai.ai_path(cid, gid, stem, file)
        meta = ai.read_sidecar(wav) if wav else None
        if meta is None or not isinstance(meta.get("params"), dict):
            raise JobError("у варіанта немає збережених параметрів (створений старим генератором)")
        return meta["params"]

    def based_on(self, cid: str, gid: str, stem: str, file: str) -> dict:
        """«На основі цього»: параметри варіанта для форми (n=1, seed збережено; нічого не запускає)."""
        d = {k: v for k, v in self.variant_params(cid, gid, stem, file).items() if k in GenParams.__dataclass_fields__}
        d["n"] = 1
        return GenParams.from_dict(d).to_dict()

    def again(self, cid: str, gid: str, lid: str, file: str) -> dict:
        """«Ще варіант»: ті самі параметри, новий випадковий seed, n=1."""
        stem = Path(lid).stem
        p = GenParams.from_dict(self.based_on(cid, gid, stem, file)).with_seed(None)
        return self.submit(cid, gid, lid, p, parent=file)

    def get(self, jid: str) -> dict:
        with self.cv:
            if jid not in self.jobs:
                raise JobError(f"невідоме завдання {jid}")
            return json.loads(json.dumps(self.jobs[jid]))

    def list(self, states=None) -> list[dict]:
        with self.cv:
            out = [json.loads(json.dumps(r)) for r in self._ordered()]
        eta.annotate(out, self.timing)                              # оцінка часу — з урахуванням усієї черги
        return [r for r in out if not states or r["state"] in states]

    def cancel(self, jid: str) -> dict:
        with self.cv:
            rec = self.jobs.get(jid)
            if rec is None:
                raise JobError(f"невідоме завдання {jid}")
            if rec["state"] in TERMINAL:
                return dict(rec)
            if rec["state"] == "queued":
                rec.update(state="cancelled", finished=now())
                self._save(rec)
            else:
                self._cancel.add(jid)
                eng = self._engine
        if rec["state"] == "cancelled":
            self._emit(rec, "state")
        elif eng is not None:
            eng.cancel()                                          # убиває підпроцес робітника
        return self.get(jid)

    # ------------------------------------------------------------ виконання
    def _lock_path(self) -> Path:
        return self.dir / "gpu.lock"

    def _acquire(self) -> bool:
        p = self._lock_path()
        try:
            owner = int(json.loads(p.read_text(encoding="utf-8"))["pid"])
            if owner != os.getpid() and pid_alive(owner):
                return False
        except (OSError, ValueError, KeyError, TypeError):
            pass
        p.write_text(json.dumps({"pid": os.getpid()}), encoding="utf-8")
        return True

    def _release(self) -> None:
        self._lock_path().unlink(missing_ok=True)

    def busy_elsewhere(self) -> bool:
        try:
            owner = int(json.loads(self._lock_path().read_text(encoding="utf-8"))["pid"])
        except (OSError, ValueError, KeyError, TypeError):
            return False
        return owner != os.getpid() and pid_alive(owner)

    def run_next(self) -> dict | None:
        """Виконує найстаріше `queued` синхронно. None — черга порожня або GPU зайнятий іншим процесом."""
        with self.cv:
            rec = next((r for r in self._ordered() if r["state"] == "queued"), None)
            if rec is None or not self._acquire():
                return None
            self._current = rec["id"]
        try:
            self._run(rec)
        finally:
            with self.cv:
                self._current, self._engine = None, None
                self._cancel.discard(rec["id"])
            self._release()
        return self.get(rec["id"])

    def run_all(self) -> list[dict]:
        out = []
        while (r := self.run_next()) is not None:
            out.append(r)
        return out

    def _progress(self, rec: dict, **kw) -> None:
        with self.cv:
            rec["progress"].update(kw, t=time.time())
            self._save(rec)
        self._emit(rec, "progress", progress=dict(rec["progress"]))

    def _run(self, rec: dict) -> None:
        self._set(rec, state="running", started=now(), error=None)
        try:
            results = self._execute(rec)
        except Cancelled:
            self._set(rec, state="cancelled", finished=now())
        except Exception as ex:      # noqa: BLE001 — будь-який збій = failed із поясненням, черга живе далі
            self._set(rec, state="failed", error=f"{type(ex).__name__}: {ex}", finished=now())
        else:
            if rec["id"] in self._cancel:
                self._set(rec, state="cancelled", results=results, finished=now())
            else:
                self._set(rec, state="done", results=results, finished=now())

    def _check_cancel(self, rec: dict) -> None:
        if rec["id"] in self._cancel:
            raise Cancelled("скасовано")

    def _execute(self, rec: dict) -> list[dict]:
        p = GenParams.from_dict(rec["params"])
        config.require_consent()
        eng = self.engine_factory(p.engine)
        with self.cv:
            self._engine = eng
        eng.check_ready()
        self._check_cancel(rec)
        cid, gid, lid = rec["cid"], rec["gid"], rec["lid"]
        mapped, unsupported = eng.map_params(p)
        ln = self.svc.line(cid, gid, lid)
        e = self.svc.store(cid).entry(gid, lid)
        line_text = (e["ua_text"] if e["ua_text"] is not None else ln.ua_hint).strip()
        eff = GenParams(text_override=p.text_override if "text_override" in mapped else None,
                        style=p.style if "style" in mapped else None, n=p.n, engine=p.engine)
        text, plain = eff.text_for(line_text), eff.plain_for(line_text)
        if not plain:
            raise ParamsError("порожній текст репліки: задайте text_override")
        temp, top_p = p.sampling() if "variability" in mapped else (0.7, 0.7)
        d = ai.ai_dir(cid, gid)
        k0 = max((int(m["k"]) for f in (d.glob(f"{ln.stem}.ai*.wav") if d.is_dir() else []) if (m := ai.AI_RE.match(f.name))), default=0)
        with tempfile.TemporaryDirectory(prefix="wc3ua-aistudio-") as td:
            tmp = Path(td)
            rf = refs.resolve(self.svc, cid, gid, lid, p.ref_takes if "ref_takes" in mapped else None, tmp)
            jobs = [aigen.Job(cid, gid, lid, ln.stem, k0 + 1 + i, text, plain, s, temp, top_p, eff.style, max_new=int(80 + 50 * max(ln.ru_dur, 0.5)),
                              refs=rf, out=d / f"{ln.stem}.ai{k0 + 1 + i}.wav",
                              params={**p.to_dict(), "seed": s, "temperature": temp, "top_p": top_p, "text_sent": text})
                    for i, s in enumerate(p.seeds(rec["base_seed"]))]
            self._progress(rec, total=len(jobs), done=0, phase="loading")
            made = self._generate(rec, eng, jobs, tmp, ln, unsupported)
            self._check_cancel(rec)
            self._progress(rec, phase="metrics")
            t0 = time.time()
            try:
                aigen.fill_metrics(self.svc, cid, gid, made, eng, self.asr_factory(), tmp, lambda *_: None)
                if made:
                    self.timing.learn(rec["engine"], "metrics", (time.time() - t0) / len(made))
            except Cancelled:
                raise
            except Exception as ex:      # noqa: BLE001 — метрики необов'язкові: варіанти вже збережені
                self._emit(rec, "log", message=f"метрики пропущено: {ex}")
        return [self._result(j) for j in made]

    def _generate(self, rec, eng, jobs, tmp, ln, unsupported) -> list:
        todo, made = list(jobs), []
        for attempt in range(RETRIES + 1):
            if not todo:
                break
            raws = {i: tmp / f"raw{attempt}-{i}.wav" for i in range(len(todo))}

            seen = [0]

            if attempt:
                self._progress(rec, phase="loading")        # повтор — двигун знову вантажить модель

            def on_msg(m, seen=seen):
                if isinstance(m, dict) and "out" in m:
                    pr = rec["progress"]
                    if pr.get("phase") == "generating":          # без "sec" — проміжок між варіантами
                        self.timing.learn(rec["engine"], "per", m.get("sec") or time.time() - pr.get("t", time.time()))
                    elif m.get("sec"):
                        self.timing.learn(rec["engine"], "per", m["sec"])
                    seen[0] += 1
                    self._progress(rec, done=min(pr["total"], seen[0]), phase="generating")
                elif isinstance(m, dict) and "loaded" in m:
                    self.timing.learn(rec["engine"], "load", m["loaded"])
                    self._progress(rec, phase="generating")
                    self._emit(rec, "log", message=f"модель завантажено за {m['loaded']} с")

            eng.generate(todo, raws, on_msg)
            self._check_cancel(rec)
            failed = []
            for i, j in enumerate(todo):
                ok = raws[i].exists() and aigen.postprocess(self.svc, j, raws[i])
                if ok and duration(j.out) > aigen.max_dur(ln):
                    j.out.unlink(missing_ok=True)
                    ok = False
                if not ok:
                    failed.append(replace(j, seed=(j.seed + 1000) % (SEED_MAX + 1)))
                    continue
                ai.write_sidecar(j.out, {
                    "ai": True, "engine": eng.info.name, "model": eng.info.name, "license": eng.info.output_license, "seed": j.seed,
                    "temperature": j.temperature, "style": f"[{j.style}]" if j.style else None, "ref_takes": [r["take"] for r in j.refs], "refs": [{"take": r["take"], "key": r.get("key"), "approved": r.get("approved")} for r in j.refs],
                    "text": j.plain, "cer": None, "similarity": None, "dur": round(duration(j.out), 3), "created": now(),
                    "params": j.params, "job": rec["id"], "parent": rec.get("parent"), "unsupported": unsupported})
                made.append(j)
            todo = failed
        if not made:
            raise EngineError("двигун не дав придатного звуку (усі спроби збились)")
        return made

    @staticmethod
    def _result(j) -> dict:
        m = ai.read_sidecar(j.out) or {}
        return {"file": j.out.name, "n": j.k, "seed": j.seed, "cer": m.get("cer"), "similarity": m.get("similarity"),
                "dur": m.get("dur"), "engine": m.get("engine"), "license": m.get("license")}

    # ------------------------------------------------------------ фоновий потік
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop = False
        self._thread = threading.Thread(target=self._loop, name="ai-queue", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop = True
        with self.cv:
            self.cv.notify_all()
        if self._thread:
            self._thread.join(timeout=5)

    def _loop(self) -> None:
        while not self._stop:
            if self.run_next() is None:
                with self.cv:
                    if not self._stop:
                        self.cv.wait(timeout=2.0)
