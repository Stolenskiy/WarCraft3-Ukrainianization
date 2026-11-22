"""HTTP-маршрути ШІ-студії та текстового пакета (/api/ai/*, /api/text/*) на фейкових двигунах і тимчасових теках. Без моделей і мережі."""
import json
import time

import gameconf
import install_pack
import pytest
import textpack
from aistudio import config
from aistudio import engines as E
from aistudio.api import AiStudio
from aistudio.jobs import JobQueue
from conftest import TMP_ROOT, synth
from test_aistudio import FakeCloud, FakeEngine
from test_studio_core import api  # noqa: F401  (HTTP-клієнт)

CID, GID, LID = "units-orc", "peon", "peonyes1.wav"
LINE = {"cid": CID, "gid": GID, "lid": LID}


class Asr:
    def transcribe(self, paths):
        return {str(p): "Зроблю." for p in paths}


@pytest.fixture
def ai(svc, api):  # noqa: F811
    config.settings_path().unlink(missing_ok=True)
    FakeEngine.block, FakeEngine.calls = None, []
    E.register(FakeEngine)
    E.register(FakeCloud)
    for lid in ("peonyes2.wav", "peonyes3.wav"):
        f = svc.add_take(CID, GID, lid, synth(TMP_ROOT / "own.wav", 0.9).read_bytes())["takes"][-1]["file"]
        svc.approve(CID, GID, lid, f)
    svc._aistudio = AiStudio(svc, JobQueue(svc, TMP_ROOT / "audio/ai/.jobs", asr_factory=Asr))
    yield api
    svc._aistudio.queue.stop()
    E.unregister("fake-local")
    E.unregister("fake-cloud")


def wait_job(call, jid, states=("done", "failed", "cancelled")):
    for _ in range(100):
        j = call(f"/api/ai/job?id={jid}")[1]
        if j["state"] in states:
            return j
        time.sleep(0.1)
    raise AssertionError(f"завдання {jid} не завершилось: {j}")


def test_status_and_engines(ai):
    code, st = ai("/api/ai/status")
    assert code == 200 and st["consent"] is False and "consent_text" in st and st["schema"]["max_n"] == 8
    names = {e["name"]: e for e in ai("/api/ai/engines")[1]}
    assert {"fish-s2-pro", "fake-local", "fake-cloud"} <= set(names)
    assert names["fake-cloud"]["status"]["state"] == "missing_key" and names["fake-local"]["commercial"] is True


def test_generate_needs_consent_then_runs_to_variant(ai):
    code, d = ai("/api/ai/generate", {**LINE, "params": {"engine": "fake-local", "n": 2}})
    assert code == 400 and "згода" in d["error"]                                         # без згоди — 400, нічого не в черзі
    assert ai("/api/ai/consent", {"accept": True}) == (200, {"ai_consent": True})
    code, job = ai("/api/ai/generate", {**LINE, "params": {"engine": "fake-local", "n": 2, "text_override": "Зроблю!"}})
    assert code == 200 and job["state"] in ("queued", "running") and job["license"] == "CC BY 4.0"
    done = wait_job(ai, job["id"])
    assert done["state"] == "done" and len(done["results"]) == 2
    assert [j["id"] for j in ai("/api/ai/jobs?state=done")[1]] == [job["id"]] and ai("/api/ai/jobs?state=queued")[1] == []
    evs = ai("/api/ai/events?after=0")[1]
    assert evs and ai(f"/api/ai/events?after={evs[-1]['id']}")[1] == []
    line = next(x for x in ai(f"/api/group/{CID}/{GID}")[1]["lines"] if x["id"] == LID)
    assert len(line["ai"]) == 2 and line["ai"][0]["engine"] == "fake-local"
    f = line["ai"][0]["file"]
    code, p = ai("/api/ai/based-on", {**LINE, "file": f})
    assert code == 200 and p["n"] == 1 and p["text_override"] == "Зроблю!" and p["engine"] == "fake-local"
    again = ai("/api/ai/again", {**LINE, "file": f})[1]
    assert wait_job(ai, again["id"])["state"] == "done" and again["parent"] == f
    assert ai("/api/ai/based-on", {**LINE, "file": "nope.ai9.wav"})[0] == 400
    code, adopted = ai("/api/ai/adopt", {**LINE, "file": f})                              # старі маршрути працюють
    assert code == 200 and any(t["source"] == "ai" for t in adopted["takes"])


def test_errors_are_400_and_unknown_job(ai):
    config.set_consent(True)
    assert ai("/api/ai/generate", {**LINE, "params": {"n": 99, "engine": "fake-local"}})[0] == 400
    assert ai("/api/ai/generate", {**LINE, "params": {"engine": "nope-engine"}})[0] == 400
    assert ai("/api/ai/generate", {**LINE, "params": {"engine": "fake-local", "ref_takes": ["../reference/x.wav"]}})[0] == 400
    assert ai("/api/ai/job?id=zzz")[0] == 404
    assert ai("/api/ai/cancel", {"id": "zzz"})[0] == 400
    assert ai("/api/ai/engine", {"name": "nope-engine"})[0] == 400


def test_cancel_queued_job(ai):
    config.set_consent(True)
    job = ai("/api/ai/generate", {**LINE, "params": {"engine": "fake-local"}})[1]          # потік уже стартував; другий — у черзі або в роботі
    j2 = ai("/api/ai/generate", {**LINE, "params": {"engine": "fake-local", "n": 8}})[1]
    c = ai("/api/ai/cancel", {"id": j2["id"]})[1]
    assert c["state"] in ("cancelled", "running")
    wait_job(ai, job["id"])
    assert wait_job(ai, j2["id"])["state"] in ("cancelled", "done")


def test_engine_settings_key_never_returned_and_cloud_consent(ai):
    config.set_consent(True)
    code, e = ai("/api/ai/engine", {"name": "fake-cloud", "api_key": "SECRET-KEY-123", "upload_consent": False})
    assert code == 200 and "SECRET" not in json.dumps(e) and e["status"]["state"] == "ready" and e["upload_consent"] is False
    code, d = ai("/api/ai/generate", {**LINE, "params": {"engine": "fake-cloud"}})
    assert code == 400 and "ВИВАНТАЖЕНО" in d["error"]
    assert ai("/api/ai/engine", {"name": "fake-cloud", "upload_consent": True})[1]["upload_consent"] is True
    job = ai("/api/ai/generate", {**LINE, "params": {"engine": "fake-cloud", "style": "whisper"}})[1]
    assert job["unsupported"] == ["style"] and any("не підтримує" in w for w in job["warnings"])
    assert (config.settings_path().parent / "settings.json").is_file() and "SECRET-KEY-123" in config.settings_path().read_text()
    wait_job(ai, job["id"])


def test_ref_candidates(ai):
    code, rows = ai(f"/api/ai/refs?cid={CID}&gid={GID}&lid={LID}")
    assert code == 200 and len(rows) == 2 and all("path" not in r and r["approved"] for r in rows)
    assert ai(f"/api/ai/refs?cid={CID}&gid={GID}&lid={LID}&approved=1")[1] == rows


# ---------------------------------------------------------------- текстовий пакет (prepare підмінено: без мережі)
@pytest.fixture
def game(tmp_path, monkeypatch):
    g = tmp_path / "wc3"
    (g / "Data").mkdir(parents=True)
    monkeypatch.setenv("WC3_GAME_ROOT", str(g))
    src = tmp_path / "src"
    for rel, txt in {"Units/OrcUnitStrings.txt": "[opeo]\nName=Піон\n", "UI/FrameDef.fdf": "x"}.items():
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text(txt, encoding="utf-8")
    res = textpack.BuildResult(files={r: src / r for r in ("Units/OrcUnitStrings.txt", "UI/FrameDef.fdf")},
                               stats={"hotkeys": {"markers_added": 7, "tips_changed": 3, "sections_changed": 2}},
                               skipped=["x: невідома тека"], source={"commit": "a" * 40, "variant": "light", "archive_sha256": "b" * 64})

    def fake_prepare(tid, full=False, ref=None, game=None, log=print, **kw):
        log("кеш: готово")
        target = textpack.load_target(tid)
        return target, game, install_pack.target_root(target, game), res
    monkeypatch.setattr(install_pack, "prepare", fake_prepare)
    return g


def wait_text(call, jid):
    for _ in range(100):
        j = call(f"/api/text/job?id={jid}")[1]
        if j["state"] != "running":
            return j
        time.sleep(0.05)
    raise AssertionError("план тексту завис")


def test_text_targets_plan_apply_uninstall(game, api):  # noqa: F811
    code, t = api("/api/text/targets")
    assert code == 200 and t["valid"] and t["detected"] == "classic-1.31" and {x["id"] for x in t["targets"]} >= {"classic-1.31", "reforged"}
    assert next(x for x in t["targets"] if x["id"] == "classic-1.31")["installed"] is None
    assert api("/api/text/apply", {"id": "zzz"})[0] == 400                                 # без плану нічого не пишемо
    job = api("/api/text/plan", {"target": "classic-1.31"})[1]
    done = wait_text(api, job["id"])
    pl = done["plan"]
    assert done["state"] == "ready" and pl["commit"] == "a" * 40 and pl["new"] == 2 and pl["hotkeys"]["markers_added"] == 7
    assert pl["status"] == "supported" and "_res" not in done and not (game / "Units").exists()   # сухий прогін нічого не записав
    code, r = api("/api/text/apply", {"id": job["id"]})
    assert code == 200 and r["installed"] == 2 and "uninstall" in r["rollback"]
    assert (game / "Units/OrcUnitStrings.txt").read_text(encoding="utf-8").startswith("[opeo]")
    assert api("/api/text/apply", {"id": job["id"]})[0] == 400                              # двічі той самий план — ні
    assert api("/api/text/targets")[1]["targets"][0]["installed"]["files"] == 2
    assert api("/api/text/uninstall", {"target": "classic-1.31"})[1]["removed"] == 2
    assert not (game / "Units/OrcUnitStrings.txt").exists()


def test_text_errors_and_target_detection(game, api, monkeypatch):  # noqa: F811
    assert api("/api/text/plan", {"target": "nope"})[0] == 400
    assert api("/api/text/job?id=zzz")[0] == 404
    (game / "_retail_").mkdir()
    assert api("/api/text/targets")[1]["detected"] == "reforged"

    def boom(*a, **k):
        raise textpack.TextPackError("мережа недоступна")
    monkeypatch.setattr(install_pack, "prepare", boom)
    j = wait_text(api, api("/api/text/plan", {"target": "classic-1.31"})[1]["id"])
    assert j["state"] == "error" and "мережа" in j["error"]
    monkeypatch.setattr(install_pack, "prepare", lambda *a, **k: 1 / 0)
    assert "ZeroDivisionError" in wait_text(api, api("/api/text/plan", {"target": "classic-1.31"})[1]["id"])["error"]
    monkeypatch.setattr(gameconf, "get_game_root", lambda *a: game / "Data")
    assert api("/api/text/uninstall", {"target": "reforged"})[0] == 400                      # немає _retail_ у цій «грі»
