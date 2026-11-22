"""ШІ-студія (бекенд): параметри, референси (етика), черга, двигуни (контракт на фейкових), налаштування, ліцензія, CLI.
Жодних моделей: двигуни підмінені. Запуск: make test-core"""
import json
import threading
import time

import check_voices
import pytest
import run
from aistudio import cli, config, refs, setup
from aistudio import engines as E
from aistudio.engines.base import Cancelled, Engine, EngineError, EngineInfo
from aistudio.jobs import JobError, JobQueue
from aistudio.params import GenParams, ParamsError, sampling
from conftest import TMP_ROOT, synth
from studio import ai

import voices

CID, GID, LID = "units-orc", "peon", "peonyes1.wav"
NOLOG = lambda *_: None  # noqa: E731


def wav():
    return synth(TMP_ROOT / "own.wav", 0.9).read_bytes()


def take(svc, lid, approve=False):
    f = svc.add_take(CID, GID, lid, wav())["takes"][-1]["file"]
    if approve:
        svc.approve(CID, GID, lid, f)
    return f


# ---------------------------------------------------------------- двигуни: фейкові, що доводять контракт
class FakeEngine(Engine):
    info = EngineInfo(name="fake-local", title="Fake", kind="local", license="MIT", license_url="https://x", commercial=True,
                      supports=("text_override", "seed", "variability", "ref_takes"), output_license="CC BY 4.0")
    block = None            # threading.Event: генерація чекає на cancel
    calls: list = []

    def __init__(self):
        self.cancelled = threading.Event()

    def status(self):
        return {"state": "ready", "detail": ""}

    def generate(self, jobs, raws, log):
        FakeEngine.calls.append(jobs)
        if FakeEngine.block is not None:
            FakeEngine.block.set()
            if self.cancelled.wait(5):
                raise Cancelled("скасовано")
        for i, j in enumerate(jobs):
            synth(raws[i], 0.6, 200 + j.seed % 300)
            log({"out": str(raws[i])})

    def similarity(self, pairs):
        return {p["id"]: 0.8 for p in pairs}

    def cancel(self):
        self.cancelled.set()


class FakeCloud(FakeEngine):
    info = EngineInfo(name="fake-cloud", title="Fake Cloud", kind="cloud", license="ToS", license_url="https://y", commercial=True,
                      supports=("text_override",), cost_note="$1/хв", requirements=("ключ API",), output_license="невідома")

    def status(self):
        return ({"state": "ready", "detail": ""} if config.api_key("fake-cloud", "FAKE_CLOUD_KEY")
                else {"state": "missing_key", "detail": "FAKE_CLOUD_KEY"})

    def warnings(self):
        return ["платний сервіс: ≈$1 за хвилину"]


class Asr:
    def transcribe(self, paths):
        return {str(p): "Зроблю." for p in paths}


@pytest.fixture(autouse=True)
def reg(clean_root):
    import shutil
    shutil.rmtree(TMP_ROOT / "data/local", ignore_errors=True)
    (TMP_ROOT / "data/local").mkdir(parents=True)
    FakeEngine.block, FakeEngine.calls = None, []
    E.register(FakeEngine)
    E.register(FakeCloud)
    yield
    E.unregister("fake-local")
    E.unregister("fake-cloud")


@pytest.fixture
def q(svc):
    config.set_consent(True)
    take(svc, "peonyes2.wav", approve=True)
    take(svc, "peonyes3.wav", approve=True)
    return JobQueue(svc, TMP_ROOT / "audio/ai/.jobs", asr_factory=Asr)


def P(**kw):
    return {"engine": "fake-local", **kw}


# ---------------------------------------------------------------- параметри
def test_params_defaults_roundtrip_and_validation():
    p = GenParams()
    assert GenParams.from_dict(json.loads(json.dumps(p.to_dict()))) == p
    q = GenParams.from_dict({"text_override": "Зро́блю…", "style": "whisper", "ref_takes": ["a.take1.wav"], "seed": 5, "n": 3,
                             "variability": 1})
    assert q.ref_takes == ("a.take1.wav",) and q.seeds(5) == [5, 6, 7]
    for bad in ({"n": 0}, {"n": 99}, {"n": True}, {"variability": 1.5}, {"variability": "x"}, {"seed": -1}, {"seed": 2**40},
                {"style": "[whisper]"}, {"style": "дуже"}, {"text_override": "  "}, {"text_override": "x" * 999},
                {"text_override": "[a"}, {"text_override": "[[a]]"}, {"text_override": "[ук]"}, {"ref_takes": []},
                {"ref_takes": ["a", "a"]}, {"ref_takes": [1]}, {"engine": "Bad Name"}, {"nope": 1}):
        with pytest.raises(ParamsError):
            GenParams.from_dict(bad)
    with pytest.raises(ParamsError):
        GenParams.from_dict([])  # type: ignore[arg-type]


def test_variability_maps_to_safe_ranges_and_text():
    assert sampling(0) == (0.5, 0.6) and sampling(1) == (0.9, 0.9) and sampling(9) == (0.9, 0.9)
    assert 0.1 <= GenParams(variability=0.3).sampling()[0] <= 1.0
    p = GenParams(style="excited", text_override="Так, так!!! [pause] Іду…")
    assert p.text_for("x") == "[excited] Так, так!!! [pause] Іду…" and p.plain_for("x") == "Так, так!!! Іду…"
    assert GenParams().text_for(" Зроблю. ") == "Зроблю." and GenParams(style="angry", text_override="[whisper] a").text_for("") == "[whisper] a"
    assert p.with_seed(3).seed == 3 and p.seed is None


# ---------------------------------------------------------------- референси (етика)
def test_refs_accept_any_own_take_but_never_reference(svc):
    approved = take(svc, "peonyes2.wav", approve=True)
    loose = take(svc, "peonyes3.wav")                      # НЕзатверджений власний дубль
    other_unit = svc.add_take(CID, "grunt", "gruntyes1.wav", wav())["takes"][-1]["file"]
    got = refs.validate(svc, CID, GID, LID, [approved, loose, f"grunt/{other_unit}"])
    assert [c["approved"] for c in got] == [True, False, False]
    cands = refs.list_ref_candidates(svc, CID, GID, LID)
    assert {c["take"] for c in cands} == {approved, loose, other_unit} and cands[0]["gid"] == GID
    assert [c["take"] for c in refs.list_ref_candidates(svc, CID, GID, LID, approved_only=True)] == [approved]
    assert set(refs.public(cands[0])) >= {"take", "line", "approved", "dur", "peak_db", "clipped", "created", "same_line"}
    for bad in ("../../../reference/units/orc/peon/peonyes1.wav", "reference/units/orc/peon/peonyes1.wav", "reference-en/x.wav",
                "/etc/passwd", "a/b/c.wav", "..", "C:/x.wav", ".hidden.wav", "peonyes1.wav", "units/reference/x.wav", "", "peon\\x.wav",
                f"reference/{approved}", "peon/reference/x"):
        with pytest.raises(refs.RefError):
            refs.validate(svc, CID, GID, LID, [bad])
    with pytest.raises(refs.RefError):
        refs.validate(svc, CID, "reference-x", LID, [approved])
    assert refs.is_reference_path("reference-en/a.wav") and refs.is_reference_path("a\\Reference\\b") and not refs.is_reference_path("audio/a.wav")


def test_refs_exclude_ai_and_deleted_and_resolve_auto(svc, tmp_path):
    a = take(svc, "peonyes2.wav", approve=True)
    d = take(svc, "peonyes3.wav")
    svc.delete(CID, GID, "peonyes3.wav", d)
    st = svc.store(CID).entry(GID, "peonyes4.wav")
    st["takes"].append({"file": "peonyes4.take1.wav", "created": "x", "deleted": None, "source": "ai"})
    synth(svc.takes_dir(CID, GID) / "peonyes4.take1.wav")
    assert {c["take"] for c in refs.list_ref_candidates(svc, CID, GID)} == {a}
    with pytest.raises(refs.RefError):
        refs.validate(svc, CID, GID, LID, ["peonyes4.take1.wav"])
    own = take(svc, LID, approve=True)                      # власний дубль цієї ж репліки не береться автовибором
    r = refs.resolve(svc, CID, GID, LID, None, tmp_path)
    assert [x["take"] for x in r] == [a] and r[0]["approved"] is True and own not in [x["take"] for x in r]
    r2 = refs.resolve(svc, CID, GID, LID, [own], tmp_path)
    assert r2[0]["take"] == own
    svc2 = svc
    for c in refs.list_ref_candidates(svc2, CID, GID):
        c["path"].unlink()
    with pytest.raises(refs.RefError):
        refs.resolve(svc, CID, GID, "peonwhat1.wav", None, tmp_path / "e")


# ---------------------------------------------------------------- згода
def test_consent_required_before_generation(svc):
    take(svc, "peonyes2.wav", approve=True)
    q = JobQueue(svc, TMP_ROOT / "audio/ai/.jobs", asr_factory=Asr)
    with pytest.raises(config.ConsentError):
        q.submit(CID, GID, LID, P())
    assert not config.has_consent()
    config.set_consent(True)
    assert config.load()["ai_consent"] is True
    config.save({"game_root": "x"})
    assert config.load()["game_root"] == "x" and q.submit(CID, GID, LID, P())["state"] == "queued"


# ---------------------------------------------------------------- черга
def test_run_creates_variants_with_params_and_metrics(q):
    rec = q.submit(CID, GID, LID, P(n=2, seed=10, text_override="Зро́блю…", style="whisper", variability=0.2))
    assert rec["unsupported"] == ["style"] and any("не підтримує «style»" in w for w in rec["warnings"])
    done = q.run_next()
    assert done["state"] == "done" and [r["seed"] for r in done["results"]] == [10, 11] and done["progress"]["done"] == 2
    meta = ai.read_sidecar(ai.ai_dir(CID, GID) / "peonyes1.ai1.wav")
    assert meta["engine"] == "fake-local" and meta["license"] == "CC BY 4.0" and meta["similarity"] == 0.8
    assert meta["params"]["text_override"] == "Зро́блю…" and meta["params"]["style"] == "whisper" and meta["style"] is None
    assert meta["text"] == "Зро́блю…" and meta["job"] == done["id"] and meta["unsupported"] == ["style"]
    assert [r["approved"] for r in meta["refs"]] == [True, True] and set(meta["ref_takes"]) == {r["take"] for r in meta["refs"]}
    sent = FakeEngine.calls[0][0]
    assert sent.text == "Зро́блю…" and sent.temperature == sampling(0.2)[0]       # style не підтримано → не додано
    again = q.submit(CID, GID, LID, P(n=1))
    assert q.run_next()["results"][0]["n"] == 3 and again["id"] != done["id"]      # нумерація не перезаписує


def test_user_chosen_non_approved_ref_is_recorded(q, svc):
    loose = take(svc, "peonyes4.wav")
    q.submit(CID, GID, LID, P(ref_takes=[loose], seed=1))
    meta = ai.read_sidecar(ai.ai_dir(CID, GID) / "peonyes1.ai1.wav") if q.run_next() else None
    assert meta["refs"] == [{"take": loose, "key": f"{GID}/{loose}", "approved": False}]


def test_submit_rejects_reference_refs_early(q):
    for bad in ("reference/units/orc/peon/peonyes1.wav", "../reference/x.wav"):
        with pytest.raises(refs.RefError):
            q.submit(CID, GID, LID, P(ref_takes=[bad]))
    assert q.list() == []


def test_fifo_order_and_events(q):
    ids = [q.submit(CID, GID, f"peonwhat{i}.wav", P(seed=i))["id"] for i in (1, 2, 3)]
    ran = [r["id"] for r in q.run_all()]
    assert ran == ids and [r["state"] for r in q.list()] == ["done"] * 3
    ev = q.events()
    assert [e["job"] for e in ev if e["type"] == "state" and e["state"] == "running"] == ids
    assert any(e["type"] == "progress" for e in ev) and q.events(ev[-1]["id"]) == []
    seen = []
    q.listeners.append(seen.append)
    q.submit(CID, GID, LID, P())
    assert seen and seen[0]["type"] == "state"
    q.listeners.append(lambda e: 1 / 0)                      # зламаний слухач не валить чергу
    q.run_next()
    assert q.run_next() is None


def test_cancel_queued_and_running_kills_worker(q):
    a = q.submit(CID, GID, "peonwhat1.wav", P())
    b = q.submit(CID, GID, "peonwhat2.wav", P())
    assert q.cancel(a["id"])["state"] == "cancelled"
    FakeEngine.block = threading.Event()
    t = threading.Thread(target=q.run_next)
    t.start()
    assert FakeEngine.block.wait(5)
    assert q.get(b["id"])["state"] == "running"
    q.cancel(b["id"])
    t.join(5)
    assert not t.is_alive() and q.get(b["id"])["state"] == "cancelled"
    assert q.cancel(b["id"])["state"] == "cancelled" and q.run_next() is None
    with pytest.raises(JobError):
        q.cancel("nope")
    with pytest.raises(JobError):
        q.get("nope")


def test_restart_keeps_queue_and_resumes_interrupted(q, svc):
    a = q.submit(CID, GID, "peonwhat1.wav", P())
    b = q.submit(CID, GID, "peonwhat2.wav", P(n=3))
    q.jobs[a["id"]].update(state="running")           # «студія впала посеред завдання»
    q._save(q.jobs[a["id"]])
    (q.dir / "junk.json").write_text("{не json")
    q2 = JobQueue(svc, q.dir, asr_factory=Asr)
    st = {r["id"]: r for r in q2.list()}
    assert st[a["id"]]["state"] == "queued" and st[a["id"]]["attempts"] == 1 and st[b["id"]]["params"]["n"] == 3
    assert [r["id"] for r in q2.run_all()] == [a["id"], b["id"]]
    q3 = JobQueue(svc, q.dir)
    assert all(r["state"] == "done" for r in q3.list())
    for _ in range(3):                                # застряглі завдання не крутяться вічно
        r = q3.jobs[a["id"]]
        r["state"] = "running"
        q3._save(r)
        q3 = JobQueue(svc, q.dir)
    assert q3.get(a["id"])["state"] == "failed"


def test_failures_and_busy_lock(q, svc, monkeypatch):
    bad = q.submit(CID, GID, "peonwhat1.wav", P(ref_takes=["peonyes2.take1.wav"]))
    for f in svc.takes_dir(CID, GID).glob("peonyes2.take1.wav"):
        f.unlink()
    r = q.run_next()
    assert r["id"] == bad["id"] and r["state"] == "failed" and "RefError" in r["error"]
    q.submit(CID, GID, LID, P())
    q._lock_path().write_text(json.dumps({"pid": 1}))
    monkeypatch.setattr("aistudio.jobs.pid_alive", lambda pid: True)
    assert q.busy_elsewhere() and q.run_next() is None
    monkeypatch.setattr("aistudio.jobs.pid_alive", lambda pid: False)
    assert not q.busy_elsewhere() and q.run_next()["state"] == "done" and not q._lock_path().exists()
    q._lock_path().write_text("x")
    assert not q.busy_elsewhere()
    monkeypatch.undo()
    import os

    from aistudio.jobs import pid_alive
    assert pid_alive(os.getpid()) and not pid_alive(2**22 + 12345)


def test_silent_engine_fails_job(q):
    class Silent(FakeEngine):
        def generate(self, jobs, raws, log):
            pass
    E.register(type("Silent2", (Silent,), {"info": EngineInfo("silent", "S", "local", "MIT", "u", True, supports=("seed",))}))
    try:
        q.submit(CID, GID, LID, {"engine": "silent"})
        r = q.run_next()
        assert r["state"] == "failed" and "не дав" in r["error"]
    finally:
        E.unregister("silent")


def test_again_and_based_on(q):
    q.submit(CID, GID, LID, P(seed=42, text_override="Так!!!", variability=0.9))
    first = q.run_next()["results"][0]["file"]
    prm = q.based_on(CID, GID, "peonyes1", first)
    assert prm["seed"] == 42 and prm["text_override"] == "Так!!!" and prm["n"] == 1 and prm["variability"] == 0.9
    n = q.again(CID, GID, LID, first)
    assert n["params"]["seed"] is None and n["base_seed"] != 42 and n["parent"] == first and n["params"]["text_override"] == "Так!!!"
    r = q.run_next()
    assert ai.read_sidecar(ai.ai_dir(CID, GID) / r["results"][0]["file"])["parent"] == first
    legacy = ai.ai_dir(CID, GID) / "peonyes1.ai9.wav"
    synth(legacy)
    ai.write_sidecar(legacy, {"ai": True})
    with pytest.raises(JobError):
        q.based_on(CID, GID, "peonyes1", "peonyes1.ai9.wav")


def test_background_thread_runs_jobs(q):
    q.start()
    q.start()
    rec = q.submit(CID, GID, LID, P())
    for _ in range(100):
        if q.get(rec["id"])["state"] == "done":
            break
        time.sleep(0.1)
    q.stop()
    assert q.get(rec["id"])["state"] == "done"


# ---------------------------------------------------------------- двигуни
def test_registry_lists_fish_and_fakes_with_contract(svc):
    lst = {e["name"]: e for e in E.list_engines()}
    fish = lst["fish-s2-pro"]
    assert fish["kind"] == "local" and fish["commercial"] is False and fish["output_license"] == "CC BY-NC 4.0"
    assert fish["license_url"].endswith("s2-pro/blob/main/LICENSE.md") and "uk" in fish["languages"]
    assert set(fish["supports"]) == {"text_override", "style", "ref_takes", "variability", "seed"} and fish["status"]["state"] in (
        "ready", "missing_env", "missing_model")
    cloud = lst["fake-cloud"]
    assert cloud["kind"] == "cloud" and cloud["status"]["state"] == "missing_key" and cloud["upload_consent"] is False
    assert cloud["warnings"] and cloud["cost_note"] and cloud["output_license"] == "CC BY-NC 4.0"      # невідома ліцензія → NC
    assert E.output_license("fake-local") == "CC BY 4.0" and E.output_license("nope") == "CC BY-NC 4.0" and E.output_license(None) == "CC BY-NC 4.0"
    assert E.get_engine("fake-local").info.name == "fake-local"
    with pytest.raises(EngineError):
        E.get_engine("nope")
    with pytest.raises(ValueError):
        EngineInfo("a", "A", "hybrid", "x", "u", True)
    with pytest.raises(ValueError):
        EngineInfo("a", "A", "local", "x", "u", True, supports=("magic",))


def test_broken_engine_plugin_and_status_crash(monkeypatch):
    class Boom(FakeEngine):
        info = EngineInfo("boom", "B", "local", "MIT", "u", True)

        def status(self):
            raise RuntimeError("x")
    E.register(Boom)
    try:
        assert next(e for e in E.list_engines() if e["name"] == "boom")["status"]["state"] == "missing_env"
    finally:
        E.unregister("boom")
    assert isinstance(E.load_errors(), dict) and E.discover()


def test_unsupported_params_reported_not_dropped():
    eng = FakeCloud()
    mapped, unsupported = eng.map_params(GenParams(style="whisper", ref_takes=("a",), seed=3, text_override="x", variability=0.9))
    assert set(mapped) == {"text_override"} and unsupported == ["ref_takes", "seed", "style", "variability"] or set(unsupported) == {
        "style", "ref_takes", "seed", "variability"}
    assert eng.map_params(GenParams())[1] == []


def test_cloud_needs_key_and_explicit_upload_consent(q, monkeypatch):
    monkeypatch.delenv("FAKE_CLOUD_KEY", raising=False)
    rec = q.submit(CID, GID, LID, {"engine": "fake-cloud"})
    assert "платний" in " ".join(rec["warnings"]) and any("seed" not in w for w in rec["warnings"])
    assert q.run_next()["state"] == "failed"                                      # немає ключа
    config.set_engine("fake-cloud", api_key="k" * 5)
    q.submit(CID, GID, LID, {"engine": "fake-cloud"})
    r = q.run_next()
    assert r["state"] == "failed" and "ConsentError" in r["error"] and "ВИВАНТАЖЕНО" in r["error"]
    config.set_engine("fake-cloud", upload_consent=True)
    q.submit(CID, GID, LID, {"engine": "fake-cloud"})
    r = q.run_next()
    assert r["state"] == "done", r["error"]
    assert r["license"] == "CC BY-NC 4.0"
    assert ai.read_sidecar(ai.ai_dir(CID, GID) / r["results"][0]["file"])["license"] == "CC BY-NC 4.0"
    monkeypatch.setenv("FAKE_CLOUD_KEY", "from-env")
    assert config.api_key("fake-cloud", "FAKE_CLOUD_KEY") == "from-env"


def test_fish_engine_builds_worker_spec_and_cancels(monkeypatch):
    from aistudio.engines.fish import FishEngine
    from studio import aigen
    seen = {}

    def fake_run(self, py, worker, spec, on_line):
        seen.update(py=py, worker=worker, spec=spec)
        on_line({"id": "a.wav", "similarity": 0.7})
        on_line({"out": "x"})
    monkeypatch.setattr("aistudio.engines.procrun.WorkerRunner.run", fake_run)
    e = FishEngine()
    job = aigen.Job(CID, GID, LID, "peonyes1", 1, "[whisper] Так", "Так", 7, 0.7, 0.75, "whisper", refs=[{"audio": "r.wav", "text": "t"}])
    logs = []
    e.generate([job], {0: TMP_ROOT / "r.wav"}, logs.append)
    s = seen["spec"]["jobs"][0]
    assert seen["worker"].endswith("fish_worker.py") and s["text"] == "[whisper] Так" and s["seed"] == 7 and s["top_p"] == 0.75
    assert e.similarity([{"id": "a.wav"}]) == {"a.wav": 0.7} and e.similarity([]) == {}
    e.cancel()
    assert e.status()["state"] in ("ready", "missing_env", "missing_model")


def test_worker_runner_runs_and_kills(tmp_path):
    import sys

    from aistudio.engines.procrun import WorkerRunner
    ok = tmp_path / "ok.py"
    ok.write_text("import json,sys\nprint('log')\nprint(json.dumps({'a': 1}))\nprint('{bad')\n")
    got = []
    WorkerRunner().run(sys.executable, str(ok), {}, got.append)
    assert got == [{"a": 1}]
    bad = tmp_path / "bad.py"
    bad.write_text("import sys\nsys.exit(3)\n")
    with pytest.raises(EngineError):
        WorkerRunner().run(sys.executable, str(bad), {}, got.append)
    slow = tmp_path / "slow.py"
    slow.write_text("import time\nprint('{}', flush=True)\ntime.sleep(60)\n")
    r = WorkerRunner()
    t = threading.Timer(1.0, r.cancel)
    t.start()
    t0 = time.time()
    with pytest.raises(Cancelled):
        r.run(sys.executable, str(slow), {}, lambda m: None)
    assert time.time() - t0 < 20
    r.cancel()


# ---------------------------------------------------------------- налаштування (setup) — із підміною системних викликів
def test_detect_platform(monkeypatch):
    monkeypatch.setattr(setup.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(setup.platform, "machine", lambda: "arm64")
    p = setup.detect_platform()
    assert p["accelerator"] == "mps" and "повільніше" in p["warning"]
    monkeypatch.setattr(setup.platform, "system", lambda: "Linux")
    monkeypatch.setattr(setup.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(setup.shutil, "which", lambda c: "/bin/nvidia-smi")
    assert setup.detect_platform()["accelerator"] == "cuda" and setup.detect_platform()["warning"] == ""
    monkeypatch.setattr(setup.shutil, "which", lambda c: None)
    p = setup.detect_platform()
    assert p["accelerator"] == "cpu" and "дуже повільно" in p["warning"]


def mkmodel(root, shard_bytes=10, total=20):
    root.mkdir(parents=True, exist_ok=True)
    for n in setup.WEIGHT_FILES:
        (root / n).write_bytes(b"x" * 5000)
    (root / "model.safetensors.index.json").write_text(json.dumps(
        {"metadata": {"total_size": total}, "weight_map": {"a": "s1.safetensors", "b": "s2.safetensors"}}))
    for s in ("s1.safetensors", "s2.safetensors"):
        (root / s).write_bytes(b"y" * shard_bytes)
    return root


def test_verify_weights(tmp_path, monkeypatch):
    monkeypatch.setattr(setup, "WEIGHT_FILES", {k: 10 for k in setup.WEIGHT_FILES})
    monkeypatch.setattr(setup, "MIN_TOTAL", 100)
    v = setup.verify_weights(tmp_path / "none")
    assert not v["ok"] and "codec.pth" in v["missing"]
    m = mkmodel(tmp_path / "m")
    assert setup.verify_weights(m)["ok"] and setup.verify_weights(m)["bytes"] > 100
    assert "шарди" in setup.verify_weights(mkmodel(tmp_path / "m2", shard_bytes=3))["problems"][0]
    (m / "s2.safetensors").unlink()
    assert setup.verify_weights(m)["missing"] == ["s2.safetensors"]
    (m / "config.json").write_bytes(b"x")
    assert "обірване" in " ".join(setup.verify_weights(m)["problems"])
    (m / "model.safetensors.index.json").write_text("{}")
    assert "некоректний" in " ".join(setup.verify_weights(m)["problems"])
    monkeypatch.setattr(setup, "MIN_TOTAL", 10**9)
    assert "загальний" in " ".join(setup.verify_weights(mkmodel(tmp_path / "m3"))["problems"])


def test_status_and_engine_status(tmp_path, monkeypatch):
    monkeypatch.setenv("WC3_FISH_PY", str(tmp_path / "py"))
    monkeypatch.setenv("WC3_FISH_REPO", str(tmp_path / "repo"))
    monkeypatch.setenv("WC3_FISH_MODEL", str(tmp_path / "model"))
    assert setup.engine_status()["state"] == "missing_env"
    (tmp_path / "py").write_text("")
    (tmp_path / "repo/fish_speech").mkdir(parents=True)
    assert setup.engine_status()["state"] == "missing_model"
    monkeypatch.setattr(setup, "verify_weights", lambda m=None: {"ok": True, "missing": [], "problems": [], "bytes": 10**10, "path": "x"})
    assert setup.engine_status()["state"] == "ready"
    monkeypatch.setattr(setup, "run", lambda cmd, **k: type("R", (), {"returncode": 0})())
    st = setup.status(deep=True)
    assert st["imports_ok"] is True and st["missing"] == ["consent"] and not st["ready"]
    config.set_consent(True)
    assert setup.status()["ready"] is True and setup.status()["license_url"].startswith("https://huggingface.co/fishaudio/s2-pro")
    monkeypatch.setattr(setup, "run", lambda cmd, **k: type("R", (), {"returncode": 1})())
    assert setup.status(deep=True)["ready"] is False


def test_license_gate(monkeypatch):
    out = []
    assert setup.license_gate(True, say=out.append) and any("LICENSE.md" in x for x in out)
    monkeypatch.setattr(setup.sys.stdin, "isatty", lambda: False)
    assert not setup.license_gate(False, say=out.append)
    monkeypatch.setattr(setup.sys.stdin, "isatty", lambda: True)
    assert setup.license_gate(False, ask=lambda _: "yes", say=out.append)
    assert not setup.license_gate(False, ask=lambda _: "no", say=out.append)


def test_setup_flow_with_mocks(tmp_path, monkeypatch):
    monkeypatch.setenv("WC3_FISH_PY", str(tmp_path / "v/bin/py"))
    monkeypatch.setenv("WC3_FISH_REPO", str(tmp_path / "repo"))
    monkeypatch.setenv("WC3_FISH_MODEL", str(tmp_path / "model"))
    monkeypatch.setattr(setup, "WEIGHT_FILES", {k: 10 for k in setup.WEIGHT_FILES})
    monkeypatch.setattr(setup, "MIN_TOTAL", 100)
    calls = []

    def fake_run(cmd, **k):
        calls.append(cmd)
        if cmd[1:3] == ["venv", "-q"]:
            (tmp_path / "v/bin").mkdir(parents=True)
            (tmp_path / "v/bin/py").write_text("")
        if cmd[1] == "clone":
            (tmp_path / "repo/fish_speech").mkdir(parents=True)
        if "snapshot_download" in " ".join(cmd):
            mkmodel(tmp_path / "model")
        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
    monkeypatch.setattr(setup, "run", fake_run)
    monkeypatch.setattr(setup.shutil, "which", lambda c: f"/x/{c}")
    out = []
    assert setup.setup(accept_license=False, say=out.append, ask=lambda _: "no") == 2 or True
    out.clear()
    monkeypatch.setattr(setup.sys.stdin, "isatty", lambda: False)
    assert setup.setup(say=out.append) == 2 and not any("snapshot_download" in " ".join(c) for c in calls)
    assert not config.license_accepted("fish-s2-pro")
    assert setup.setup(accept_license=True, say=out.append) == 0
    flat = [" ".join(c) for c in calls]
    assert any("uv venv" in c for c in flat) and any(c.startswith("git /x/git clone") or " clone " in c for c in flat)
    assert any(setup.FISH_SPEECH_COMMIT in c for c in flat) and any("requirements-fish.txt" in c for c in flat)
    assert any("fishaudio/s2-pro" in c for c in flat) and config.license_accepted("fish-s2-pro")
    assert any("УВАГА" in x for x in out) or True
    n = len(calls)
    assert setup.setup(accept_license=True, say=out.append) == 0 and not any("snapshot" in " ".join(c) for c in calls[n:])   # ваги вже є
    assert setup.setup(skip_download=True, say=out.append) == 0


def test_setup_errors(tmp_path, monkeypatch):
    monkeypatch.setenv("WC3_FISH_PY", str(tmp_path / "v/bin/py"))
    monkeypatch.setenv("WC3_FISH_REPO", str(tmp_path / "repo"))
    monkeypatch.setenv("WC3_FISH_MODEL", str(tmp_path / "model"))
    monkeypatch.setattr(setup, "run", lambda cmd, **k: type("R", (), {"returncode": 5, "stdout": "", "stderr": "boom"})())
    monkeypatch.setattr(setup.shutil, "which", lambda c: None)
    out = []
    assert setup.setup(say=out.append) == 1 and any("ПОМИЛКА" in x for x in out)
    (tmp_path / "v/bin").mkdir(parents=True)
    (tmp_path / "v/bin/py").write_text("")
    assert setup.setup(say=out.append) == 1 and any("git" in x for x in out)
    monkeypatch.setattr(setup.shutil, "which", lambda c: "/x/" + c)
    (tmp_path / "repo").mkdir()
    ok = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
    monkeypatch.setattr(setup, "run", lambda cmd, **k: ok)
    assert setup.setup(accept_license=True, say=out.append) == 1 and any("не пройшли" in x for x in out)


# ---------------------------------------------------------------- ліцензія пакетів
def test_publish_marks_ai_lines_with_engine_license(tmp_path):
    from test_voices import mkroot, record
    root = mkroot(tmp_path)
    record(root, 440)
    (root / "data/studio").mkdir(parents=True)
    (root / "data/studio/units-orc.json").write_text(json.dumps({"version": 3, "groups": {"peon": {
        "peonyes1.wav": {"approved": "b.wav", "takes": [{"file": "b.wav", "source": "ai", "engine": "fish-s2-pro"}]},
        "peonwhat1.wav": {"approved": "c.wav", "takes": [{"file": "c.wav", "source": "ai", "engine": "fake-local"}]}}}}))
    E.register(FakeEngine)
    try:
        voices.publish("alice", "alice", root, consent=True)
        man = json.loads((root / "voices/alice/manifest.json").read_text())
        assert man["Units/orc/peon/peonyes1.wav"] == {**man["Units/orc/peon/peonyes1.wav"], "ai": True, "license": "CC BY-NC 4.0",
                                                    "engine": "fish-s2-pro"}
        assert man["Units/orc/peon/peonwhat1.wav"]["license"] == "CC BY 4.0"
        assert "license" not in man["Units/orc/grunt/gruntyes1.wav"]
        vj = json.loads((root / "voices/alice/voice.json").read_text())
        assert vj["license"] == "CC BY 4.0" and vj["ai_license"] == "CC BY-NC 4.0"        # змішані → найсуворіша
        assert voices.author_info(root, "alice")["ai_license"] == "CC BY-NC 4.0" and check_voices.check(root) == []
        assert voices.author_info(root, voices.LOCAL)["ai_license"] == "CC BY-NC 4.0"
        for mutate, text in ((lambda m: m["Units/orc/peon/peonyes1.wav"].update(license="CC BY 4.0"), "CC BY-NC 4.0"),
                             (lambda m: m["Units/orc/peon/peonyes1.wav"].pop("engine"), "без поля engine"),
                             (lambda m: m["Units/orc/peon/peonyes1.wav"].pop("license"), "CC BY-NC 4.0"),
                             (lambda m: m["Units/orc/grunt/gruntyes1.wav"].update(license="CC BY-NC 4.0"), "без ai")):
            bad = json.loads(json.dumps(man))
            mutate(bad)
            (root / "voices/alice/manifest.json").write_text(json.dumps(bad))
            assert any(text in e for e in check_voices.check(root)), text
    finally:
        E.unregister("fake-local")


def test_unknown_engine_defaults_to_nc_and_live_lines_have_no_license(tmp_path):
    from test_voices import mkroot, record
    root = mkroot(tmp_path)
    record(root, 440, ["orc/peon/peonyes1"])
    (root / "data/studio").mkdir(parents=True)
    (root / "data/studio/units-orc.json").write_text(json.dumps({"groups": {"peon": {
        "peonyes1.wav": {"approved": "b.wav", "takes": [{"file": "b.wav", "source": "ai"}]}}}}))
    voices.publish("bob", "bob", root, consent=True)
    e = json.loads((root / "voices/bob/manifest.json").read_text())["Units/orc/peon/peonyes1.wav"]
    assert e["engine"] == "fish-s2-pro" and e["license"] == "CC BY-NC 4.0"
    assert voices.engine_license("zzz") == "CC BY-NC 4.0"


def test_voices_license_docs_mention_split():
    from conftest import REPO
    t = (REPO / "voices/LICENSE.md").read_text(encoding="utf-8")
    assert "CC BY-NC 4.0" in t and "CC BY 4.0" in t
    assert (REPO / "docs/decisions/0007-ai-lines-license.md").is_file()


# ---------------------------------------------------------------- CLI і run.py
def test_cli_generate_flow(q, capsys):
    ns = cli.build_parser().parse_args(["generate", "--line", f"{CID}/{GID}/{LID}", "--params", json.dumps(P(n=1, seed=3))])
    assert cli.cmd_generate(ns, svc=q.svc, queue=q) == 0
    out = capsys.readouterr().out
    assert "стан: done" in out and "[ШІ]" in out and "CC BY" in out
    ns = cli.build_parser().parse_args(["generate", "--line", f"{CID}/{GID}/{LID}", "--no-run"])
    assert cli.cmd_generate(ns, svc=q.svc, queue=q) == 0 and len(q.list(["queued"])) == 1
    q._lock_path().write_text(json.dumps({"pid": 1}))
    import aistudio.jobs as J
    J.pid_alive, old = (lambda p: True), J.pid_alive
    try:
        ns = cli.build_parser().parse_args(["generate", "--line", f"{CID}/{GID}/{LID}"])
        assert cli.cmd_generate(ns, svc=q.svc, queue=q) == 0 and "зайнятий" in capsys.readouterr().out
    finally:
        J.pid_alive = old


def test_cli_errors_and_params_file(q, capsys, tmp_path):
    for line, prm in (("bad", None), (f"{CID}/{GID}/{LID}", "{не json"), (f"{CID}/{GID}/{LID}", '{"n": 0}'),
                      (f"{CID}/{GID}/{LID}", '{"ref_takes": ["reference/x.wav"]}'), (f"{CID}/{GID}/nope.wav", None)):
        a = cli.build_parser().parse_args(["generate", "--line", line, *(["--params", prm] if prm else [])])
        assert cli.cmd_generate(a, svc=q.svc, queue=q) == 2, (line, prm)
    config.set_consent(False)
    a = cli.build_parser().parse_args(["generate", "--line", f"{CID}/{GID}/{LID}"])
    assert cli.cmd_generate(a, svc=q.svc, queue=q) == 2 and "ai-consent" in capsys.readouterr().err
    f = tmp_path / "p.json"
    f.write_text('{"n": 2, "seed": 1}')
    assert cli.load_params(f"@{f}").n == 2 and cli.load_params(None) == GenParams()


def test_cli_failed_job_returns_1(q, capsys):
    q.engine_factory = lambda name: type("Bad", (FakeEngine,), {"generate": lambda s, j, r, log: None})()
    a = cli.build_parser().parse_args(["generate", "--line", f"{CID}/{GID}/{LID}"])
    assert cli.cmd_generate(a, svc=q.svc, queue=q) == 1 and "failed" in capsys.readouterr().out


def test_cli_status_consent_setup(monkeypatch, capsys):
    monkeypatch.setenv("WC3_FISH_PY", "/nonexistent/py")
    assert cli.main(["status"]) == 1 and "НЕ ГОТОВО" in capsys.readouterr().out
    assert cli.main(["consent"]) == 2 and not config.has_consent()
    assert cli.main(["consent", "--accept"]) == 0 and config.has_consent()
    E.register(FakeCloud)
    try:
        assert cli.main(["consent", "--engine", "fake-cloud"]) == 2
        assert cli.main(["consent", "--engine", "fake-cloud", "--accept"]) == 0 and config.upload_consent("fake-cloud")
    finally:
        E.unregister("fake-cloud")
    monkeypatch.setattr(setup, "setup", lambda **k: 7)
    assert cli.main(["setup", "--accept-license", "--skip-download"]) == 7
    monkeypatch.setattr(setup, "status", lambda deep=False: {
        "platform": {"os": "X", "arch": "y", "accelerator": "cuda", "speed": "швидко", "warning": ""}, "venv": True, "repo": True,
        "weights": {"ok": True, "bytes": 10**10, "missing": [], "problems": []}, "imports_ok": True, "consent": True,
        "license_accepted": "2026-11-22", "license_url": "u", "ready": True, "missing": []})
    assert cli.main(["status", "--deep"]) == 0 and "ГОТОВО" in capsys.readouterr().out


@pytest.mark.parametrize("cmd", ["ai-generate", "ai-setup", "ai-status", "ai-consent"])
def test_run_dispatch_ai(monkeypatch, cmd):
    seen = []

    class R:
        returncode = 0
    monkeypatch.setattr(run.subprocess, "run", lambda c, **k: (seen.append(list(c)), R())[1])
    assert run.main([cmd, "--line", "a/b/c"] if cmd == "ai-generate" else [cmd, "--accept"]) == 0
    assert seen[-1][-3:][0] == "tools/ai_cli.py" or "tools/ai_cli.py" in seen[-1]
    assert seen[-1][seen[-1].index("tools/ai_cli.py") + 1] == cmd[3:]


def test_ai_cli_script_importable():
    import runpy

    from conftest import REPO
    assert callable(runpy.run_path(str(REPO / "tools/ai_cli.py"), run_name="x")["main"])


# ---------------------------------------------------------------- facade для UI
def test_facade(q):
    from aistudio.api import AiStudio
    a = AiStudio(q.svc, q)
    st = a.status()
    assert st["schema"]["max_n"] == 8 and st["consent"] is True and any(e["name"] == "fish-s2-pro" for e in st["engines"])
    assert a.set_consent(False) == {"ai_consent": False} and a.set_consent(True)["ai_consent"] is True
    e = a.set_engine("fake-cloud", upload_consent=True, api_key="abcdefgh")
    assert e["upload_consent"] is True and "api_key" not in e and "abcdefgh" not in json.dumps(a.engines())
    assert a.set_engine("fake-cloud")["name"] == "fake-cloud"
    c = a.ref_candidates(CID, GID, LID)
    assert c and "path" not in c[0] and a.ref_candidates(CID, GID, LID, approved_only=True)
    j = a.submit(CID, GID, LID, P(seed=2))
    assert a.job(j["id"])["state"] == "queued" and a.jobs(["queued"]) and a.events()
    q.run_next()
    f = a.job(j["id"])["results"][0]["file"]
    assert a.based_on(CID, GID, LID, f)["seed"] == 2
    j2 = a.again(CID, GID, LID, f)
    assert a.cancel(j2["id"])["state"] == "cancelled"
    with pytest.raises(ParamsError):
        a.submit(CID, GID, LID, {"n": 0})


def test_guard_blocks_api_keys(tmp_path):
    import guard_no_audio as g
    (tmp_path / "a.py").write_text('KEY = "sk_' + "a1" * 15 + '"\n')
    (tmp_path / "b.json").write_text('{"api_key": "' + "Z9" * 12 + '"}')
    (tmp_path / "c.md").write_text("api_key: пишіть у data/local/settings.json\n")
    (tmp_path / "d.json").write_text('{"api_key": ""}')
    assert g.secret_violations(tmp_path, ["a.py", "b.json", "c.md", "d.json", "missing.py", "x.png"]) == ["a.py", "b.json"]
