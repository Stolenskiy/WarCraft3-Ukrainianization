"""Оцінка часу ШІ-генерації (tools/aistudio/eta.py) і як черга її вчить та віддає в /api/ai/jobs."""
import json

from aistudio import config, eta
from aistudio import engines as E
from aistudio.engines.base import EngineInfo
from aistudio.jobs import JobQueue
from conftest import TMP_ROOT, synth
from test_aistudio import CID, GID, LID, Asr, FakeEngine, take


def rec(state="running", phase="generating", done=0, total=2, t=100.0, seq=1, engine="e"):
    return {"state": state, "seq": seq, "engine": engine, "params": {"n": total},
            "progress": {"done": done, "total": total, "phase": phase, "t": t}}


def test_timing_learns_ema_persists_and_ignores_junk(tmp_path):
    t = eta.Timing(tmp_path / "timing.json")
    assert t.est("e") == eta.DEFAULT
    t.learn("e", "per", 10)
    t.learn("e", "per", 20)                                   # ковзне: 10 → 0.6·10 + 0.4·20
    t.learn("e", "load", -1), t.learn("e", "nope", 5), t.learn("e", "per", "x"), t.learn("e", "load", 99999)
    assert t.est("e") == {**eta.DEFAULT, "per": 14.0}
    assert eta.Timing(tmp_path / "timing.json").est("e")["per"] == 14.0
    (tmp_path / "bad.json").write_text("[1,")
    assert eta.Timing(tmp_path / "bad.json").est("e") == eta.DEFAULT
    ro = eta.Timing(tmp_path / "missing-dir/x.json")           # не вдалося записати — не біда
    ro.learn("e", "per", 5)
    assert ro.est("e")["per"] == 5


def test_annotate_phases_and_queue_order(tmp_path):
    t = eta.Timing(tmp_path / "t.json")
    for k, v in {"load": 10, "per": 20, "metrics": 2}.items():
        t.learn("e", k, v)
    total = 10 + 2 * (20 + 2)                                  # 54 с на завдання з двох варіантів
    jobs = [rec(phase="loading", t=100), rec(state="queued", phase="queued", seq=2), rec(state="done", seq=3)]
    eta.annotate(jobs, t, t=104)
    assert jobs[0]["eta"] == {"left": 6 + 44, "total": total, "ahead": 0}
    assert jobs[1]["eta"] == {"left": 50 + total, "total": total, "ahead": 50} and "eta" not in jobs[2]
    gen = rec(done=1, t=100)
    eta.annotate([gen], t, t=105)                              # другий з двох: 20−5 + метрики 2×2
    assert gen["eta"]["left"] == 15 + 4
    late = rec(done=0, t=0)
    eta.annotate([late], t, t=500)                             # оцінку перевищено — не від’ємна, «ще трохи»
    assert late["eta"]["left"] == 2 + 20 + 4
    m = rec(phase="metrics", done=2, t=100)
    eta.annotate([m], t, t=110)
    assert m["eta"]["left"] == 1


class Timed(FakeEngine):
    """Як Fish: {"loaded": с}, потім {"out": …, "sec": с} на кожен варіант."""
    info = EngineInfo(name="fake-timed", title="Timed", kind="local", license="MIT", license_url="https://x", commercial=True,
                      supports=("text_override", "seed"), output_license="CC BY 4.0")
    seen: list = []

    def generate(self, jobs, raws, log):
        log({"loaded": 12.0})
        for i, j in enumerate(jobs):
            synth(raws[i], 0.6, 200 + j.seed % 300)
            log({"out": str(raws[i]), "sec": 7.0})
            Timed.seen.append(dict(Timed.q.get(Timed.rid)["progress"]))


def test_queue_learns_from_engine_messages_and_exposes_eta(svc):
    config.set_consent(True)
    take(svc, "peonyes2.wav", approve=True)
    E.register(Timed)
    try:
        Timed.seen, Timed.q = [], JobQueue(svc, TMP_ROOT / "audio/ai/.jobs", asr_factory=Asr)
        Timed.rid = Timed.q.submit(CID, GID, LID, {"engine": "fake-timed", "n": 2})["id"]
        queued = Timed.q.list(["queued"])[0]
        assert queued["eta"]["left"] > 0 and queued["eta"]["ahead"] == 0
        done = Timed.q.run_next()
    finally:
        E.unregister("fake-timed")
    assert done["state"] == "done" and [(s["phase"], s["done"]) for s in Timed.seen] == [("generating", 1), ("generating", 2)]
    est = json.loads((TMP_ROOT / "audio/ai/.jobs/timing.json").read_text())["fake-timed"]
    assert est["load"] == 12.0 and est["per"] == 7.0 and "metrics" in est
    assert "eta" not in Timed.q.list(["done"])[0] and "t" in done["progress"]
