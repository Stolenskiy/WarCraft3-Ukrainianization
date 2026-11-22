"""ШІ-чернетка юніта / раси (tools/aistudio/draft.py, /api/ai/draft*) і прогрес «живі / ШІ / оригінал» (studio.ai.voice_kind,
`mix` у /api/catalogs). Двигуни фейкові (tests/test_aistudio.py), без моделей і мережі."""
import pytest
from aistudio import config
from aistudio import engines as E
from aistudio.api import AiStudio
from aistudio.draft import Drafts
from aistudio.jobs import JobQueue
from aistudio.refs import RefError
from conftest import TMP_ROOT, synth
from studio import ai
from test_ai_routes import wait_job
from test_aistudio import FakeCloud, FakeEngine
from test_studio_core import api  # noqa: F401  (HTTP-клієнт)

CID, GID = "units-orc", "peon"
TEXTED = [f"peon{k}{i}.wav" for k in ("yes", "what") for i in range(1, 5)]      # у фікстурі текст є лише в цих 8 репліках


class Asr:
    def transcribe(self, paths):
        return {str(p): "Зроблю." for p in paths}


def wav():
    return synth(TMP_ROOT / "own.wav", 0.9).read_bytes()


def take(svc, lid, approve=False, gid=GID):
    f = svc.add_take(CID, gid, lid, wav())["takes"][-1]["file"]
    if approve:
        svc.approve(CID, gid, lid, f)
    return f


@pytest.fixture
def eng(clean_root):
    config.settings_path().unlink(missing_ok=True)
    FakeEngine.block, FakeEngine.calls = None, []
    E.register(FakeEngine)
    E.register(FakeCloud)
    yield
    E.unregister("fake-local")
    E.unregister("fake-cloud")


@pytest.fixture
def dq(svc, eng):
    """Черга + чернетки без фонового потоку (run_all — синхронно)."""
    q = JobQueue(svc, TMP_ROOT / "audio/ai/.jobs", asr_factory=Asr)
    return Drafts(svc, q)


def test_voice_kind_priority():
    t = lambda f, **kw: {"file": f, "deleted": None, **kw}  # noqa: E731
    assert ai.voice_kind(None, False) == "orig" and ai.voice_kind({}, True) == "ai"
    assert ai.voice_kind({"takes": [t("a", source="ai")], "approved": None, "original": None}, False) == "ai"           # ШІ-дубль, не обраний
    assert ai.voice_kind({"takes": [t("a", source="ai")], "approved": "a", "original": None}, False) == "ai_game"
    assert ai.voice_kind({"takes": [t("a", source="ai"), t("b")], "approved": "a"}, False) == "ai_game"        # у грі — ШІ
    assert ai.voice_kind({"takes": [t("a", source="ai"), t("b")], "approved": None}, True) == "live"           # живий запис — пріоритет
    assert ai.voice_kind({"takes": [t("b", source="enhanced")], "approved": "b"}, True) == "live"
    assert ai.voice_kind({"takes": [], "approved": None, "original": {"lang": "ru"}}, True) == "kept"
    assert ai.voice_kind({"takes": [{"file": "b", "deleted": "x"}], "approved": None}, False) == "orig"        # кошик не рахується


def test_plan_skips_own_ai_kept_and_textless(svc, dq):
    take(svc, "peonyes2.wav", approve=True)
    take(svc, "peonyes3.wav")                                              # власний дубль без вибору — теж «живий»
    svc.keep_original(CID, GID, "peonwhat1.wav", "ru")
    d = ai.ai_dir(CID, GID)
    synth(d / "peonwhat2.ai1.wav", 0.5)
    ai.write_sidecar(d / "peonwhat2.ai1.wav", {"ai": True, "engine": "x"})
    synth(d / "peonwhat3.ai1.wav", 0.5)                                    # прихований варіант не рахується
    ai.write_sidecar(d / "peonwhat3.ai1.wav", {"ai": True, "engine": "x", "discarded": True})
    synth(d / "junk.wav", 0.5)
    assert ai.ai_stems(CID, GID) == {"peonwhat2"}
    p = dq.plan(CID, GID, "fake-local")
    g = p["groups"][0]
    assert g["todo"] == ["peonyes1.wav", "peonyes4.wav", "peonwhat3.wav", "peonwhat4.wav"]
    assert g["mix"] == {"live": 2, "ai": 1, "orig": 15, "ai_game": 0, "kept": 1, "total": 18}
    assert p["todo"] == 4 and p["refs"] == 1 and p["engine"] == "fake-local" and p["per_line"] > 0 and p["ahead"] == 0
    race = dq.plan(CID, None, "fake-local")
    assert [x["gid"] for x in race["groups"]] == [x.id for x in svc.groups(CID)] and race["todo"] == 4    # у решти юнітів немає тексту
    svc.set_text(CID, "grunt", "gruntyes1.wav", "Так, вождю!")
    assert dq.plan(CID, None, "fake-local")["todo"] == 5


def test_submit_needs_consent_and_own_voice(svc, dq):
    with pytest.raises(config.ConsentError):
        dq.submit(CID, GID, "fake-local")
    config.set_consent(True)
    with pytest.raises(RefError, match="власний дубль"):
        dq.submit(CID, GID, "fake-local")
    assert not dq.queue.jobs
    take(svc, "peonyes2.wav", approve=True)
    take(svc, "peonyes3.wav", approve=True)
    take(svc, "peonyes4.wav", approve=True)
    take(svc, "peonwhat1.wav", approve=True)
    take(svc, "peonwhat2.wav", approve=True)
    take(svc, "peonwhat3.wav", approve=True)
    take(svc, "peonwhat4.wav", approve=True)
    assert dq.submit(CID, GID, "fake-local")["queued"] == 1               # лишилась тільки peonyes1
    assert dq.submit(CID, GID, "fake-local") == {"batch": None, "queued": 0, "jobs": [], "skipped": []}   # уже в черзі — не дублюємо


def test_draft_run_approve_only_where_nothing_chosen(svc, dq):
    config.set_consent(True)
    take(svc, "peonyes2.wav", approve=True)
    svc.set_text(CID, "grunt", "gruntyes1.wav", "Так, вождю!")
    res = dq.submit(CID, None, "fake-local", approve=True)
    jobs = [dq.queue.get(j) for j in res["jobs"]]
    assert res["queued"] == 8 and res["batch"].startswith("draft-") and res["license"] == "CC BY 4.0"
    assert {j["lid"] for j in jobs} == {*TEXTED, "gruntyes1.wav"} - {"peonyes2.wav"}
    assert all(j["draft"] == {"batch": res["batch"], "approve": True} and j["params"]["n"] == 1 for j in jobs)
    peon = next(j for j in jobs if j["gid"] == GID)
    grunt = next(j for j in jobs if j["gid"] == "grunt")
    assert peon["params"]["ref_takes"] is None                            # у юніта є свої обрані — автовибір групи
    assert grunt["params"]["ref_takes"] == [f"{GID}/{svc.store(CID).entry(GID, 'peonyes2.wav')['approved']}"]   # інакше — з раси
    take(svc, "peonyes1.wav")                                             # поки чекали — записав живий дубль (не обрав)
    svc.keep_original(CID, GID, "peonwhat1.wav", "ru")
    done = dq.queue.run_all()
    assert len(done) == 8 and {j["state"] for j in done} == {"done"}
    lines = {x["id"]: x for x in svc.group_json(CID, GID)["lines"]}
    assert lines["peonyes1.wav"]["approved"] is None and lines["peonyes1.wav"]["ai"]          # живий запис — пріоритет
    assert lines["peonwhat1.wav"]["original"] and lines["peonwhat1.wav"]["approved"] is None
    w = lines["peonwhat2.wav"]
    t = next(t for t in w["takes"] if t["file"] == w["approved"])
    assert t["source"] == "ai" and t["engine"] == "fake-local" and w["game_exists"]           # ШІ-дубль обрано, позначка «ШІ»
    assert any("ШІ-чернетка" in h["action"] for h in w["history"])
    gl = svc.group_json(CID, "grunt")["lines"][0]
    assert gl["approved"] and gl["takes"][0]["source"] == "ai"
    mix = svc.voice_mix(CID, GID)
    assert mix["ai_game"] == 5 and mix["live"] == 2 and mix["kept"] == 1
    assert not dq.adopt_draft(CID, GID, "peonwhat2.wav", w["ai"][0]["file"])                   # уже обрано — нічого
    assert dq.plan(CID, GID, "fake-local")["todo"] == 0


def test_draft_without_approve_keeps_choice_empty_and_cancel(svc, dq):
    config.set_consent(True)
    take(svc, "peonyes2.wav", approve=True)
    res = dq.submit(CID, GID, "fake-local")
    assert dq.plan(CID, GID, "fake-local")["active"] == 7 and dq.plan(CID, "grunt", "fake-local")["active"] == 0
    assert dq.cancel(CID, "grunt") == {"cancelled": 0}
    assert dq.cancel(batch="nope") == {"cancelled": 0}
    dq.queue.run_next()
    assert dq.cancel(CID, GID, res["batch"]) == {"cancelled": 6}
    assert [j["state"] for j in dq.queue.list()].count("cancelled") == 6
    lines = {x["id"]: x for x in svc.group_json(CID, GID)["lines"]}
    first = dq.queue.get(res["jobs"][0])["lid"]
    assert lines[first]["ai"] and lines[first]["approved"] is None                            # без «одразу обрати» — лише варіант
    assert svc.voice_mix(CID, GID)["ai"] == 1


def test_draft_cloud_engine_without_ref_choice_skips_foreign_units(svc, dq):
    config.set_consent(True)
    config.set_engine("fake-cloud", api_key="K", upload_consent=True)
    take(svc, "peonyes2.wav", approve=True)
    svc.set_text(CID, "grunt", "gruntyes1.wav", "Так, вождю!")
    res = dq.submit(CID, None, "fake-cloud")
    assert res["queued"] == 7 and res["skipped"] == [{"gid": "grunt", "lid": "gruntyes1.wav",
                                                      "reason": "у юніта немає обраних власних дублів, а двигун не дає обрати референси"}]


# ---------------------------------------------------------------- HTTP
@pytest.fixture
def http(svc, api, eng):  # noqa: F811
    take(svc, "peonyes2.wav", approve=True)
    svc._aistudio = AiStudio(svc, JobQueue(svc, TMP_ROOT / "audio/ai/.jobs", asr_factory=Asr))
    yield api
    svc._aistudio.queue.stop()


def test_draft_routes_and_catalog_mix(http):
    code, cats = http("/api/catalogs")
    peon = next(g for g in cats[0]["groups"] if g["id"] == GID)
    assert code == 200 and peon["mix"] == {"live": 1, "ai": 0, "orig": 17, "ai_game": 0, "kept": 0, "total": 18}
    code, p = http(f"/api/ai/draft?cid={CID}&gid={GID}&engine=fake-local")
    assert code == 200 and p["todo"] == 7 and p["consent"] is False
    assert http(f"/api/ai/draft?cid={CID}&gid=nope")[0] == 404
    assert http(f"/api/ai/draft?cid={CID}&engine=nope-engine")[0] == 404
    code, d = http("/api/ai/draft", {"cid": CID, "gid": GID, "engine": "fake-local"})
    assert code == 400 and "згода" in d["error"]
    http("/api/ai/consent", {"accept": True})
    code, r = http("/api/ai/draft", {"cid": CID, "gid": GID, "engine": "fake-local", "approve": True})
    assert code == 200 and r["queued"] == 7
    for jid in r["jobs"]:
        assert wait_job(http, jid)["state"] == "done"
    peon = next(g for g in http("/api/catalogs")[1][0]["groups"] if g["id"] == GID)
    assert peon["mix"]["ai"] == 7 and peon["mix"]["ai_game"] == 7 and peon["done"] == 8
    assert http("/api/ai/draft", {"cid": CID, "gid": GID, "engine": "fake-local"})[1]["queued"] == 0
    assert http("/api/ai/draft/cancel", {"cid": CID})[1] == {"cancelled": 0}
    assert http("/api/ai/draft", {"cid": CID, "engine": "fake-cloud"})[0] == 400            # не готовий двигун — одразу 400
