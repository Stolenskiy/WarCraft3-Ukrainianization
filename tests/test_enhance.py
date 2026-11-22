"""ШІ-очищення дублів: статус і встановлення (tools/aistudio/enhance.py), черга (enhance_jobs.py), сервіс, HTTP /api/enhance/*.
Модель підміняється фейковим робітником; справжній Sidon — лише якщо встановлено (.venv-enhance + models/sidon-onnx)."""
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest
from aistudio import enhance, eta
from aistudio.engines.base import Cancelled
from aistudio.enhance_jobs import EnhanceJobError, EnhanceQueue
from conftest import TMP_ROOT, synth
from studio.svc.util import StudioError
from test_studio_core import api  # noqa: F401  (HTTP-клієнт)

CID, GID = "units-orc", "peon"
REPO = Path(__file__).resolve().parent.parent


@pytest.fixture
def installed(tmp_path, monkeypatch):
    """Фейкова «встановлена» модель: файли потрібних розмірів (розріджені) і python venv."""
    py, model = tmp_path / "venv/bin/python", tmp_path / "model"
    py.parent.mkdir(parents=True)
    py.write_text("")
    for name, size in enhance.MODEL_FILES.items():
        (model / name).parent.mkdir(parents=True, exist_ok=True)
        with open(model / name, "wb") as f:
            f.truncate(size)
    monkeypatch.setenv("WC3_ENHANCE_PY", str(py))
    monkeypatch.setenv("WC3_ENHANCE_MODEL", str(model))
    return py, model


class FakeRunner:
    """Як WorkerRunner + sidon_worker: пише 48 кГц файл у кожен out, звітує {"loaded"}, {"out","sec"}; fail — імена in з помилкою."""
    fail: set = set()
    block = None
    seen: list = []

    def __init__(self):
        self.cancelled = False

    def run(self, py, worker, spec, on_line):
        FakeRunner.seen.append((py, worker, spec))
        on_line({"loaded": 0.5})
        on_line({"noise": 1})
        on_line({"out": "/elsewhere.wav", "sec": 1})
        for j in spec["jobs"]:
            if FakeRunner.block is not None:
                FakeRunner.block.wait(5)
                if self.cancelled:
                    raise Cancelled("скасовано")
            if Path(j["in"]).name in FakeRunner.fail:
                on_line({"out": j["out"], "error": "ValueError: зламано"})
                continue
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", j["in"], "-af", "volume=-12dB", "-ar", "48000", j["out"]], check=True)
            on_line({"out": j["out"], "sec": 0.3})

    def cancel(self):
        self.cancelled = True
        if FakeRunner.block is not None:
            FakeRunner.block.set()


@pytest.fixture
def q(svc, installed, tmp_path):
    FakeRunner.fail, FakeRunner.block, FakeRunner.seen = set(), None, []
    svc._enhance = EnhanceQueue(svc, eta.Timing(tmp_path / "t.json"), runner_factory=FakeRunner,
                                setup_fn=lambda say: say("крок установки"))
    return svc._enhance


def take(svc, lid, sec=0.9, approve=False):
    f = svc.add_take(CID, GID, lid, synth(TMP_ROOT / "own.wav", sec).read_bytes())["takes"][-1]["file"]
    if approve:
        svc.approve(CID, GID, lid, f)
    return f


def wait(q, jid, states=("done", "failed", "cancelled")):
    for _ in range(200):
        j = next(x for x in q.list() if x["id"] == jid)
        if j["state"] in states:
            return j
        time.sleep(0.05)
    raise AssertionError(j)


# ---------------------------------------------------------------- статус і встановлення
def test_status_states(tmp_path, monkeypatch):
    monkeypatch.setenv("WC3_ENHANCE_PY", str(tmp_path / "nope/python"))
    monkeypatch.setenv("WC3_ENHANCE_MODEL", str(tmp_path / "m"))
    st = enhance.status()
    assert st["state"] == "missing_env" and st["license"] == "MIT" and st["download_mb"] > 100
    (tmp_path / "python").write_text("")
    monkeypatch.setenv("WC3_ENHANCE_PY", str(tmp_path / "python"))
    assert enhance.status()["state"] == "missing_model" and "int8/sidon-predictor.onnx" in enhance.status()["detail"]
    monkeypatch.delenv("WC3_ENHANCE_PY")
    assert enhance.paths()["py"].parent.parent.name == ".venv-enhance"


def test_setup_uv_and_pip_paths_download_and_errors(tmp_path, monkeypatch):
    py, model = tmp_path / "venv/bin/python", tmp_path / "model"
    monkeypatch.setenv("WC3_ENHANCE_PY", str(py))
    monkeypatch.setenv("WC3_ENHANCE_MODEL", str(model))
    calls, said = [], []

    def run(cmd, **kw):
        calls.append(cmd)
        if "venv" in cmd:
            py.parent.mkdir(parents=True, exist_ok=True)
            py.write_text("")
        if "-c" in cmd:                                     # «завантаження»
            for name, size in enhance.MODEL_FILES.items():
                (model / name).parent.mkdir(parents=True, exist_ok=True)
                with open(model / name, "wb") as f:
                    f.truncate(size)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    assert enhance.setup(say=said.append, run=run, uv="/bin/uv")["state"] == "ready"
    assert calls[0][:3] == ["/bin/uv", "venv", "--python"] and calls[1][:3] == ["/bin/uv", "pip", "install"]
    assert enhance.HF_REVISION in calls[2] and enhance.HF_REPO in calls[2] and "готово" in said[-1]
    calls.clear()
    enhance.setup(say=said.append, run=run, uv="")                       # без uv: pip у venv, модель уже є — без завантаження
    assert calls == [[str(py), "-m", "pip", "install", "-r", str(enhance.REQUIREMENTS)]]
    with pytest.raises(enhance.EnhanceError, match="ставлю"):
        enhance.setup(say=said.append, run=lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, "", "no wheel"), uv="")
    shutil.rmtree(model)
    with pytest.raises(enhance.EnhanceError, match="після встановлення"):
        enhance.setup(say=said.append, run=lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, "", ""), uv="")
    py.unlink()
    enhance.setup(say=said.append, run=run, uv="")
    assert calls[-3][1:3] != ["venv"] and "-m" in calls[-3] and "venv" in calls[-3]


def test_requirements_pinned():
    lines = [x for x in enhance.REQUIREMENTS.read_text().splitlines() if x and not x.startswith("#")]
    assert lines and all("==" in x for x in lines) and not any(x.startswith("torch") for x in lines)


def test_finish_levels_to_target_and_game_format(tmp_path):
    raw = synth(tmp_path / "raw.wav", 1.0)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(raw), "-af", "volume=-8dB", "-ar", "48000", str(tmp_path / "q.wav")], check=True)
    gain = enhance.finish(tmp_path / "q.wav", tmp_path / "out.wav")
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=sample_rate,channels,sample_fmt", "-of", "csv=p=0",
                          str(tmp_path / "out.wav")], capture_output=True, text=True).stdout.strip()
    assert out == "s16,22050,1" and gain > 2 and abs(enhance.loudness(tmp_path / "out.wav") - enhance.TARGET_LUFS) < 1.5
    (tmp_path / "bad.wav").write_bytes(b"nope")
    assert enhance.loudness(tmp_path / "bad.wav") is None
    with pytest.raises(enhance.EnhanceError):
        enhance.finish(tmp_path / "bad.wav", tmp_path / "x.wav")
    assert not (tmp_path / "x.tmp.wav").exists()


def test_loudness_survives_missing_ffmpeg(monkeypatch, tmp_path):
    monkeypatch.setattr(enhance.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(OSError("no ffmpeg")))
    assert enhance.loudness(tmp_path / "x.wav") is None


# ---------------------------------------------------------------- черга і сервіс
def test_clean_creates_new_takes_copies_trim_tempo_and_approves(svc, q):
    f1 = take(svc, "peonyes1.wav", approve=True)
    svc.set_trim(CID, GID, "peonyes1.wav", f1, 0.05, 0.8)
    svc.set_tempo(CID, GID, "peonyes1.wav", f1, 1.1)
    f2 = take(svc, "peonyes2.wav")
    j = q.submit([{"cid": CID, "gid": GID, "lid": "peonyes1.wav", "file": f1}, {"cid": CID, "gid": GID, "lid": "peonyes2.wav", "file": f2}],
                 approve=True)
    assert j["state"] == "queued" and "items" not in j
    j = wait(q, j["id"])
    assert j["state"] == "done" and j["done"] == 2 and j["failed"] == 0 and j["keys"] == [f"{CID}/{GID}/peonyes1.wav", f"{CID}/{GID}/peonyes2.wav"]
    r1 = next(r for r in j["results"] if r["lid"] == "peonyes1.wav")
    assert r1["approved"] is True and r1["gain_db"] > 5
    ln = svc.line_json(CID, GID, svc.line(CID, GID, "peonyes1.wav"))
    new = next(t for t in ln["takes"] if t["file"] == r1["new_file"])
    assert new["source"] == "enhanced" and new["enhanced_from"] == f1 and new["engine"] == enhance.ENGINE
    assert new["tempo"] == 1.1 and new["trim"] and ln["approved"] == r1["new_file"]
    assert next(r for r in j["results"] if r["lid"] == "peonyes2.wav")["approved"] is False
    py, worker, spec = FakeRunner.seen[0]
    assert worker.endswith("sidon_worker.py") and spec["model"] == os.environ["WC3_ENHANCE_MODEL"] and len(spec["jobs"]) == 2
    assert json.loads((Path(q.timing.path)).read_text())[enhance.ENGINE]["per"] == 0.3
    assert any("ШІ-очищення" in h["action"] for h in ln["history"])


def test_partial_failure_and_validation(svc, q, monkeypatch):
    f1, f2 = take(svc, "peonyes1.wav"), take(svc, "peonyes2.wav")
    FakeRunner.fail = {f2}
    j = wait(q, q.submit([{"cid": CID, "gid": GID, "lid": "peonyes1.wav", "file": f1}, {"cid": CID, "gid": GID, "lid": "peonyes2.wav", "file": f2}])["id"])
    assert j["state"] == "done" and j["failed"] == 1 and "зламано" in next(r for r in j["results"] if r["file"] == f2)["error"]
    for bad in ([], None, [{"cid": CID}], [{"cid": CID, "gid": GID, "lid": "peonyes1.wav", "file": "nope.wav"}]):
        with pytest.raises((EnhanceJobError, StudioError)):
            q.submit(bad)
    svc.delete(CID, GID, "peonyes1.wav", f1)
    with pytest.raises(StudioError, match="кошику"):
        q.submit([{"cid": CID, "gid": GID, "lid": "peonyes1.wav", "file": f1}])
    e = svc.store(CID).entry(GID, "peonyes2.wav")
    e["takes"][0]["source"] = "ai"
    with pytest.raises(StudioError, match="згенеровано ШІ"):
        q.submit([{"cid": CID, "gid": GID, "lid": "peonyes2.wav", "file": f2}])
    monkeypatch.setenv("WC3_ENHANCE_MODEL", "/nope")
    f3 = take(svc, "peonyes3.wav")
    with pytest.raises(EnhanceJobError, match="Встановити"):
        q.submit([{"cid": CID, "gid": GID, "lid": "peonyes3.wav", "file": f3}])


def test_add_enhanced_take_rejects_empty_and_missing_file(svc, q, tmp_path):
    f = take(svc, "peonyes1.wav")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", "0.1", str(tmp_path / "s.wav")], check=True)
    with pytest.raises(StudioError, match="порожній"):
        svc.add_enhanced_take(CID, GID, "peonyes1.wav", f, tmp_path / "s.wav", engine="x")
    (svc.take_path(CID, GID, svc._take(svc.store(CID).entry(GID, "peonyes1.wav"), f))).unlink()
    with pytest.raises(StudioError, match="не знайдено"):
        svc.take_file(CID, GID, "peonyes1.wav", f)


def test_cancel_queued_and_running_setup_job_and_eta(svc, q):
    import threading
    f = take(svc, "peonyes1.wav")
    FakeRunner.block = threading.Event()
    it = [{"cid": CID, "gid": GID, "lid": "peonyes1.wav", "file": f}]
    a, b = q.submit(it), q.submit(it)
    for _ in range(100):
        if next(x for x in q.list() if x["id"] == a["id"])["phase"] == "enhancing":
            break
        time.sleep(0.02)
    ls = {x["id"]: x for x in q.list()}
    assert ls[a["id"]]["eta"]["left"] > 0 and ls[b["id"]]["eta"]["ahead"] > 0 and ls[b["id"]]["state"] == "queued"
    assert q.cancel(b["id"])["state"] == "cancelled"
    q.cancel(a["id"])
    assert wait(q, a["id"])["state"] == "cancelled"
    with pytest.raises(EnhanceJobError):
        q.cancel("nope")
    FakeRunner.block, gate = None, threading.Event()
    q.setup_fn = lambda say: (say("крок установки"), gate.wait(5))
    s = q.submit_setup()
    with pytest.raises(EnhanceJobError, match="вже йде"):
        q.submit_setup()
    gate.set()
    s = wait(q, s["id"])
    assert s["state"] == "done" and s["message"] == "крок установки"
    q.setup_fn = lambda say: (_ for _ in ()).throw(RuntimeError("мережа"))
    assert wait(q, q.submit_setup()["id"])["error"] == "мережа"


def test_eta_phases(svc, q):
    e = q._est()
    now = time.time()
    job = {"kind": "clean", "state": "running", "phase": "loading", "total": 3, "done": 0, "t": now}
    assert q._left(job, now) == pytest.approx(e["load"] + 3 * e["per"])
    assert q._left({**job, "phase": "enhancing", "done": 1}, now) == pytest.approx(e["per"] * 2)
    assert q._left({**job, "phase": "enhancing", "done": 3}, now) == 0.0
    assert q._left({"kind": "setup", "state": "queued"}, now) == 60.0
    assert 5.0 <= q._left({"kind": "setup", "state": "running", "started": now - 100}, now) <= 60.0


def test_old_finished_jobs_trimmed(svc, q):
    q.jobs = [{"id": str(i), "state": "done", "items": [], "kind": "clean"} for i in range(30)]
    q.submit_setup()
    assert len([j for j in q.jobs if j["state"] == "done"]) <= 20


# ---------------------------------------------------------------- HTTP
def test_routes(svc, q, api):  # noqa: F811
    f = take(svc, "peonyes1.wav", approve=True)
    code, st = api("/api/enhance/status")
    assert code == 200 and st["state"] == "ready" and st["jobs"] == []
    assert api("/api/enhance", {"items": []})[0] == 400
    code, j = api("/api/enhance", {"items": [{"cid": CID, "gid": GID, "lid": "peonyes1.wav", "file": f}], "approve": True})
    assert code == 200
    j = wait(q, j["id"])
    assert api("/api/enhance/jobs")[1][0]["results"][0]["approved"] is True
    assert api("/api/enhance/cancel", {"id": "nope"})[0] == 400
    assert api("/api/enhance/setup", {})[0] == 200


def test_route_queue_created_lazily(svc):
    from studio.routes import enhance as r
    q = r.queue(svc)
    assert r.queue(svc) is q and isinstance(q, EnhanceQueue)


# ---------------------------------------------------------------- справжня модель (лише якщо встановлено)
REAL_PY, REAL_MODEL = REPO / ".venv-enhance/bin/python", REPO / "models/sidon-onnx"


@pytest.mark.skipif(not REAL_PY.is_file() or bool(enhance.missing_files(REAL_MODEL)), reason="Sidon не встановлено (enhance-setup)")
def test_real_sidon_worker(tmp_path):
    from aistudio.engines.procrun import WorkerRunner
    src = synth(tmp_path / "in.wav", 1.2)
    msgs = []
    WorkerRunner().run(str(REAL_PY), str(enhance.WORKER), {"model": str(REAL_MODEL), "jobs": [{"in": str(src), "out": str(tmp_path / "o.wav")}]},
                       msgs.append)
    assert "loaded" in msgs[0] and msgs[1]["out"].endswith("o.wav") and "sec" in msgs[1]
    d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(tmp_path / "o.wav")],
                             capture_output=True, text=True).stdout)
    assert abs(d - 1.2) < 0.1
