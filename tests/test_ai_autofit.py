"""ШІ: автотривалість (темп під довжину оригіналу) і автовибір (оцінка, рейтинг, «найкращий» → у гру).
studio/aifit.py, svc/ai_svc.py, черга tools/aistudio/jobs.py, маршрути. Синтетичне аудіо й фейкові двигуни, без моделей і мережі."""
import json
import subprocess
import time
from types import SimpleNamespace

import pytest
from aistudio import config
from aistudio import engines as E
from aistudio.api import AiStudio
from aistudio.jobs import JobQueue
from conftest import TMP_ROOT, synth
from studio import ai, aifit
from studio.catalog import duration
from studio.core import StudioError
from test_aistudio import FakeCloud, FakeEngine
from test_studio_core import api  # noqa: F401  (HTTP-клієнт)

CID, GID, LID = "units-orc", "peon", "peonyes1.wav"
LINE = {"cid": CID, "gid": GID, "lid": LID}
AI_DIR = TMP_ROOT / "audio/ai" / CID / GID


def variant(k, sec=0.8, stem="peonyes1", **meta):
    w = synth(AI_DIR / f"{stem}.ai{k}.wav", sec, 300 + 20 * k)
    ai.write_sidecar(w, {"ai": True, "engine": "fake-local", "model": "m", "seed": k, "temperature": 0.7, "style": None,
                         "ref_takes": [], "text": "Зроблю.", "cer": 0.0, "similarity": 0.9, "dur": sec,
                         "created": "2026-11-22T10:00:00", "peak_db": -3.0, "clipped": False, **meta})
    return w


def own(svc, lid=LID, approve=True):
    f = svc.add_take(CID, GID, lid, synth(TMP_ROOT / "own.wav", 0.9).read_bytes())["takes"][-1]["file"]
    if approve:
        svc.approve(CID, GID, lid, f)
    return f


def line(svc):
    return svc.line_json(CID, GID, svc.line(CID, GID, LID))


class Asr:
    def transcribe(self, paths):
        return {str(p): "Зроблю." for p in paths}


@pytest.fixture
def engines(clean_root):
    config.settings_path().unlink(missing_ok=True)
    FakeEngine.block, FakeEngine.calls = None, []
    E.register(FakeEngine)
    E.register(FakeCloud)
    yield
    E.unregister("fake-local")
    E.unregister("fake-cloud")


@pytest.fixture
def q(svc, engines):
    config.set_consent(True)
    own(svc, "peonyes2.wav")
    own(svc, "peonyes3.wav")
    return JobQueue(svc, TMP_ROOT / "audio/ai/.jobs", asr_factory=Asr)


# ---------------------------------------------------------------- автотривалість: чисті функції
def test_fit_range_tolerance_and_explanations():
    same = aifit.fit(0.81, 0.8)
    assert same["tempo"] == 1.0 and same["fits"] and not same["short"] and "темп не потрібен" in same["note"]
    f = aifit.fit(0.9, 0.8)                                      # трохи довше → прискорити в межах
    assert f["tempo"] == 1.125 and f["after"] == 0.8 and f["fits"] and "×1.12" in f["note"] and "висота" in f["note"]
    long = aifit.fit(1.2, 0.8)                                   # не влазить навіть із ×1.25 — пояснюємо, а не «бурмочемо»
    assert long["tempo"] == aifit.FIT_MAX and long["need"] == 1.5 and not long["fits"] and long["after"] == 0.96
    assert "не влазить" in long["note"] and "×1.50" in long["note"] and "Скоротіть" in long["note"]
    short = aifit.fit(0.5, 0.8)                                  # закоротко: сповільнити до межі, у грі не заважає
    assert short["tempo"] == aifit.FIT_MIN and short["short"] and short["fits"] and "не заважає" in short["note"]
    slow = aifit.fit(0.7, 0.8)
    assert slow["tempo"] == 0.875 and not slow["short"]
    assert aifit.fit(None, 1) is None and aifit.fit(1, None) is None and aifit.fit(1, 0) is None


def test_score_parts_and_unknown_metrics():
    perfect = aifit.parts({"cer": 0.0, "similarity": 0.97, "clipped": False, "peak_db": -3}, aifit.fit(0.8, 0.8))
    assert perfect == {"cer": 1.0, "similarity": 1.0, "dur": 1.0, "clip": 1.0} and aifit.score(perfect) == 100
    assert aifit.parts({}, None) == {} and aifit.score({}) is None                    # нічого не відомо — без оцінки
    p = aifit.parts({"cer": 0.5, "similarity": 0.5, "clipped": True}, aifit.fit(1.2, 0.8))
    assert p["cer"] == 0 and p["similarity"] == 0 and p["clip"] == 0 and 0 < p["dur"] < 0.5
    assert aifit.parts({"clipped": False, "peak_db": -0.05}, None) == {"clip": 0.5}  # упритул до 0 дБ
    assert aifit.score({"cer": 1.0}) == 100 and aifit.score({"cer": 0.5, "dur": 1.0}) == round(100 * (0.45 * 0.5 + 0.2) / 0.65)
    longer, shorter = aifit.parts({}, aifit.fit(1.5, 1)), aifit.parts({}, aifit.fit(1 / 1.5, 1))
    assert longer["dur"] < shorter["dur"]                        # задовго гірше, ніж закоротко


def test_rank_marks_best_only_with_rivals():
    def boom():
        raise AssertionError("ціль не потрібна без варіантів")
    assert aifit.rank([], boom) == []
    vs = [{"n": 1, "cer": 0.3, "dur": 0.8}, {"n": 2, "cer": 0.0, "dur": 0.8}, {"n": 3, "dur": None}, {"n": 4, "cer": 0.0, "dur": 0.8}]
    aifit.rank(vs, lambda: 0.8)
    assert [v["rank"] for v in vs] == [3, 1, None, 2] and [v["best"] for v in vs] == [False, True, False, False]
    assert aifit.best(vs)["n"] == 2 and vs[0]["fit"]["tempo"] == 1.0 and vs[2]["fit"] is None
    one = aifit.rank([{"n": 1, "cer": 0.0}], None)
    assert one[0]["rank"] == 1 and not one[0]["best"] and aifit.best([{"n": 1}]) is None


def test_voice_dur_ignores_edge_silence_and_target_fallbacks(tmp_path):
    raw = synth(tmp_path / "raw.wav", 0.6)
    padded = tmp_path / "padded.wav"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(raw), "-af", "adelay=400,apad=pad_dur=0.5", str(padded)], check=True)
    v = aifit.voice_dur(padded)
    assert duration(padded) > 1.4 and 0.55 < v < 0.9 and aifit.voice_dur(padded) == v          # кеш
    assert aifit.voice_dur(tmp_path / "nope.wav") is None
    (tmp_path / "bad.wav").write_text("не звук")
    assert aifit.voice_dur(tmp_path / "bad.wav") is None
    assert aifit.target_dur(SimpleNamespace(ref_path=padded, ru_dur=9)) == v                 # голос оригіналу важливіший
    assert aifit.target_dur(SimpleNamespace(ref_path=tmp_path / "nope.wav", ru_dur=1.2345)) == 1.234   # транскрипт
    assert aifit.target_dur(SimpleNamespace(ref_path=tmp_path / "nope.wav", ru_dur=0.0)) is None
    assert aifit.peak_meta(raw)["clipped"] is False and aifit.peak_meta(raw)["peak_db"] < 0
    assert aifit.peak_meta(tmp_path / "bad.wav") == {"peak_db": None, "clipped": None}


# ---------------------------------------------------------------- сервіс: «Взяти в дублі» з автотривалістю, автовибір
def test_adopt_with_fit_sets_take_tempo_and_game_copy_is_stretched(svc):
    variant(1, 0.96)                                            # оригінал (фікстура) — 0.8 с голосу → треба ×1.2
    variant(2, 0.96)
    v1 = next(v for v in line(svc)["ai"] if v["n"] == 1)
    assert v1["fit"]["tempo"] == 1.2 and v1["fit"]["fits"] and v1["fit"]["target"] == pytest.approx(0.8, abs=0.03)
    res = svc.adopt_ai(CID, GID, LID, "peonyes1.ai1.wav", fit=True)
    t = res["takes"][-1]
    assert t["source"] == "ai" and t["tempo"] == 1.2 and "автотривалість" in res["history"][-1]["action"]
    plain = svc.adopt_ai(CID, GID, LID, "peonyes1.ai2.wav")["takes"][-1]   # без fit — як раніше
    assert plain["tempo"] == 1.0
    svc.approve(CID, GID, LID, t["file"])
    assert duration(svc.game_path(svc.line(CID, GID, LID))) < 0.88          # копія для гри — стиснута atempo


def test_auto_pick_takes_best_and_live_take_has_priority(svc):
    variant(1, 0.8, cer=0.4)
    variant(2, 0.8, cer=0.0)
    variant(3, 0.8, cer=0.0, similarity=0.99, discarded=True)    # приховані не беруть участі
    res = svc.auto_pick_ai(CID, GID, LID)
    k = res["picked"]
    assert k["file"] == "peonyes1.ai2.wav" and res["approved"] == k["take"] and k["tempo"] == 1.0
    assert next(t for t in res["takes"] if t["file"] == k["take"])["source"] == "ai" and res["game_exists"]
    assert "автовибір" in res["history"][-1]["action"]
    again = svc.auto_pick_ai(CID, GID, LID)                      # повторно — той самий дубль, без нових
    assert again["approved"] == k["take"] and len(again["takes"]) == len(res["takes"])
    variant(4, 0.8, cer=0.0, similarity=0.99)                    # краща нова генерація замінює ШІ-вибір
    res = svc.auto_pick_ai(CID, GID, LID, among=["peonyes1.ai4.wav"])
    assert res["picked"]["file"] == "peonyes1.ai4.wav" and res["approved"] == res["picked"]["take"] != k["take"]
    with pytest.raises(StudioError, match="among"):
        svc.auto_pick_ai(CID, GID, LID, among="peonyes1.ai4.wav")
    with pytest.raises(StudioError, match="немає оцінених"):
        svc.auto_pick_ai(CID, GID, LID, among=["nope.ai9.wav"])
    live = own(svc)                                             # живий запис завжди має пріоритет
    with pytest.raises(StudioError, match="живий дубль"):
        svc.auto_pick_ai(CID, GID, LID)
    assert line(svc)["approved"] == live
    svc.unapprove(CID, GID, LID)
    svc.keep_original(CID, GID, LID, "ru")
    with pytest.raises(StudioError, match="оригінал"):
        svc.auto_pick_ai(CID, GID, LID)


# ---------------------------------------------------------------- черга: рейтинг у результатах і автовибір після генерації
def test_job_results_ranked_and_auto_pick_after_generation(q, svc):
    job = q.submit(CID, GID, LID, {"engine": "fake-local", "n": 2}, auto_pick=True)
    assert job["auto_pick"] is True and job["pick"] is None
    done = q.run_next()
    assert done["state"] == "done" and {r["rank"] for r in done["results"]} == {1, 2}
    assert sum(r["best"] for r in done["results"]) == 1 and all(r["fit"] and r["clipped"] is False for r in done["results"])
    top = next(r for r in done["results"] if r["rank"] == 1)
    assert done["pick"]["file"] == top["file"] and line(svc)["approved"] == done["pick"]["take"]
    assert any("автовибір" in e.get("message", "") for e in q.events())
    meta = ai.read_sidecar(AI_DIR / top["file"])
    assert meta["peak_db"] < 0 and meta["clipped"] is False                    # пік — у побічному json
    plain = q.submit(CID, GID, LID, {"engine": "fake-local", "n": 1})
    assert q.run_next()["pick"] is None and plain["auto_pick"] is False


def test_job_auto_pick_skipped_when_live_take_approved(q, svc):
    live = own(svc)
    q.submit(CID, GID, LID, {"engine": "fake-local", "n": 1}, auto_pick=True)
    done = q.run_next()
    assert done["state"] == "done" and "живий дубль" in done["pick"]["skipped"] and line(svc)["approved"] == live


# ---------------------------------------------------------------- маршрути
def test_routes_adopt_fit_auto_pick_and_generate(svc, api, engines):  # noqa: F811
    variant(1, 0.96, cer=0.2)
    variant(2, 0.96, cer=0.0)
    code, res = api("/api/ai/adopt", {**LINE, "file": "peonyes1.ai1.wav", "fit": True})
    assert code == 200 and res["takes"][-1]["tempo"] == 1.2
    code, res = api("/api/ai/auto-pick", {**LINE, "fit": False})
    assert code == 200 and res["picked"]["file"] == "peonyes1.ai2.wav" and res["picked"]["tempo"] == 1.0
    best = next(v for v in res["ai"] if v["best"])
    assert best["file"] == "peonyes1.ai2.wav" and best["score"] > next(v for v in res["ai"] if not v["best"])["score"]
    own(svc)
    code, err = api("/api/ai/auto-pick", LINE)
    assert code == 400 and "живий дубль" in err["error"]
    config.set_consent(True)
    own(svc, "peonyes2.wav")
    svc._aistudio = AiStudio(svc, JobQueue(svc, TMP_ROOT / "audio/ai/.jobs", asr_factory=Asr))
    try:
        code, job = api("/api/ai/generate", {"cid": CID, "gid": GID, "lid": "peonyes4.wav", "auto_pick": True,
                                             "params": {"engine": "fake-local", "n": 2}})
        assert code == 200 and job["auto_pick"] is True
        for _ in range(100):
            j = api(f"/api/ai/job?id={job['id']}")[1]
            if j["state"] == "done":
                break
            time.sleep(0.1)
        assert j["pick"]["take"] and json.dumps(j["results"]).count('"best": true') == 1
    finally:
        svc._aistudio.queue.stop()
