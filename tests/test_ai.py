"""ШІ-варіанти: перелік, «Взяти в дублі», приховування, безпека аудіо, схема побічного json, конвеєр генерації
(двигун підмінений — жодних моделей у тестах). Запуск: make test-core"""
import json
import shutil
import threading
import urllib.error
import urllib.request

import pytest
from conftest import TMP_ROOT, synth
from studio import ai, aigen
from studio.core import StudioError

CID, GID, LID = "units-orc", "peon", "peonyes1.wav"
AI_DIR = TMP_ROOT / "audio/ai" / CID / GID


def make_ai(k=1, stem="peonyes1", **meta):
    """Синтетичний ШІ-варіант + побічний json за схемою ai.SIDECAR_KEYS."""
    AI_DIR.mkdir(parents=True, exist_ok=True)
    wav = synth(AI_DIR / f"{stem}.ai{k}.wav", 0.7, 300 + k)
    rec = {"ai": True, "engine": "fish-s2-pro", "model": "fish-s2-pro", "seed": k, "temperature": 0.7, "style": None,
           "ref_takes": ["peonyes2.take1.wav"], "text": "Зроблю.", "cer": 0.0, "similarity": 0.91, "dur": 0.7,
           "created": "2026-11-22T10:00:00", **meta}
    ai.write_sidecar(wav, rec)
    return wav


def own_wav():
    return synth(TMP_ROOT / "own-upload.wav", 0.9).read_bytes()


# ---------------------------------------------------------------- перелік і схема
def test_lines_without_ai_have_empty_list(svc):
    assert all(ln["ai"] == [] for ln in svc.group_json(CID, GID)["lines"])


def test_list_ai_per_line_with_schema(svc):
    make_ai(2)
    make_ai(1, similarity=0.85, cer=0.1, style="[cheerful]")
    make_ai(1, stem="peonyes2")
    (AI_DIR / "peonyes1.ai3.wav").write_bytes(synth(TMP_ROOT / "x.wav").read_bytes())    # без json — не показуємо
    (AI_DIR / "peonyes1.ai4.json").write_text("{не json")
    lst = svc.line_json(CID, GID, svc.line(CID, GID, LID))["ai"]
    assert [v["n"] for v in lst] == [1, 2]                         # окрема нумерація, лише цієї репліки
    assert lst[0] == {"file": "peonyes1.ai1.wav", "n": 1, "engine": "fish-s2-pro", "cer": 0.1, "similarity": 0.85,
                      "dur": 0.7, "style": "[cheerful]", "adopted": None, "discarded": False,
                      "license": None, "seed": lst[0]["seed"], "refs": None, "params": None}
    meta = json.loads((AI_DIR / "peonyes1.ai1.json").read_text())
    assert set(ai.SIDECAR_KEYS) <= set(meta) and meta["ai"] is True


def test_sidecar_must_be_marked_ai(svc):
    wav = make_ai(1)
    ai.sidecar_for(wav).write_text(json.dumps({"engine": "x"}))
    assert ai.read_sidecar(wav) is None and ai.list_ai(CID, GID, "peonyes1") == []


# ---------------------------------------------------------------- «Взяти в дублі»
def test_adopt_copies_as_new_take_with_source_ai(svc):
    own = svc.add_take(CID, GID, LID, own_wav())["takes"][0]["file"]       # take1 — власний
    make_ai(1)
    before = (AI_DIR / "peonyes1.ai1.wav").read_bytes()
    r = svc.adopt_ai(CID, GID, LID, "peonyes1.ai1.wav")
    t = r["takes"][-1]
    assert [x["file"] for x in r["takes"]] == [own, "peonyes1.take2.wav"]
    assert t["source"] == "ai" and t["engine"] == "fish-s2-pro" and r["takes"][0]["source"] is None
    assert (TMP_ROOT / "audio/self-recorded/units-orc/peon/peonyes1.take2.wav").read_bytes() == before
    assert (AI_DIR / "peonyes1.ai1.wav").exists()                           # оригінал варіанта лишається (копія)
    assert r["ai"][0]["adopted"] == "peonyes1.take2.wav"
    assert "ШІ-варіант" in r["history"][-1]["action"]
    nxt = svc.add_take(CID, GID, LID, own_wav())["takes"][-1]["file"]       # власна нумерація не збита
    assert nxt == "peonyes1.take3.wav"
    # далі — як будь-який дубль: обрізання, «Обрати для гри»
    svc.set_trim(CID, GID, LID, "peonyes1.take2.wav", 0.1, 0.6)
    assert svc.approve(CID, GID, LID, "peonyes1.take2.wav")["approved"] == "peonyes1.take2.wav"
    assert (TMP_ROOT / "game-files/Units/orc/peon/peonyes1.wav").exists()


def test_adopt_twice_and_unknown_rejected(svc):
    make_ai(1)
    svc.adopt_ai(CID, GID, LID, "peonyes1.ai1.wav")
    with pytest.raises(StudioError, match="уже взято"):
        svc.adopt_ai(CID, GID, LID, "peonyes1.ai1.wav")
    svc.delete(CID, GID, LID, "peonyes1.take1.wav")                         # видалений у кошик — можна взяти знову
    assert svc.adopt_ai(CID, GID, LID, "peonyes1.ai1.wav")["takes"][-1]["file"] == "peonyes1.take2.wav"
    for bad in ("nope.wav", "../x.wav", "peonyes2.ai1.wav"):
        with pytest.raises(StudioError):
            svc.adopt_ai(CID, GID, LID, bad)


def test_discard_hides_variant_but_keeps_file(svc):
    make_ai(1)
    make_ai(2)
    r = svc.discard_ai(CID, GID, LID, "peonyes1.ai1.wav")
    assert [v["n"] for v in r["ai"]] == [2]
    assert (AI_DIR / "peonyes1.ai1.wav").exists()
    assert svc.discard_ai(CID, GID, LID, "peonyes1.ai1.wav")["ai"][0]["n"] == 2      # повторно — без помилки
    with pytest.raises(StudioError):
        svc.discard_ai(CID, GID, LID, "ghost.wav")


# ---------------------------------------------------------------- HTTP
@pytest.fixture
def api(svc):
    from studio.server import serve
    httpd = serve(0, open_browser=False, svc=svc)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"

    def call(path, body=None):
        req = urllib.request.Request(base + path, headers={"X-Studio": "1"}, method="POST" if body is not None else "GET",
                                     data=json.dumps(body).encode() if body is not None else None)
        try:
            with urllib.request.urlopen(req) as r:
                raw = r.read()
                return r.status, (json.loads(raw) if "json" in r.headers.get("Content-Type", "") else raw)
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())
    yield call
    httpd.shutdown()


def test_api_list_audio_adopt_discard(api):
    make_ai(1)
    make_ai(2)
    code, g = api(f"/api/group/{CID}/{GID}")
    assert code == 200 and [v["file"] for v in g["lines"][next(i for i, ln in enumerate(g["lines"]) if ln["id"] == LID)]["ai"]] \
        == ["peonyes1.ai1.wav", "peonyes1.ai2.wav"]
    code, body = api(f"/audio/ai/{CID}/{GID}/peonyes1.ai1.wav")
    assert code == 200 and body[:4] == b"RIFF"
    body = {"cid": CID, "gid": GID, "lid": LID, "file": "peonyes1.ai1.wav"}
    code, ln = api("/api/ai/adopt", body)
    assert code == 200 and ln["takes"][-1]["source"] == "ai"
    assert api("/api/ai/adopt", body)[0] == 400
    code, ln = api("/api/ai/discard", {**body, "file": "peonyes1.ai2.wav"})
    assert code == 200 and [v["n"] for v in ln["ai"]] == [1]
    assert api("/api/ai/adopt", {**body, "file": "x.wav"})[0] == 400
    assert api("/api/ai/adopt", {"cid": CID})[0] == 400


def test_api_ai_audio_traversal_and_unknown(api):
    make_ai(1)
    secret = TMP_ROOT / "audio/ai/secret.wav"
    shutil.copy(AI_DIR / "peonyes1.ai1.wav", secret)
    for name in ("..%2F..%2Fsecret.wav", "..%2F..%2F..%2F..%2Fetc%2Fpasswd", "peonyes1.ai9.wav", "peonyes2.ai1.wav",
                 "%2e%2e%2fpeonyes1.ai1.wav"):
        assert api(f"/audio/ai/{CID}/{GID}/{name}")[0] == 404, name
    assert api(f"/audio/ai/{CID}/..%2F..%2Fai/peonyes1.ai1.wav")[0] == 404
    assert api(f"/audio/ai/{CID}/nogroup/peonyes1.ai1.wav")[0] == 404


# ---------------------------------------------------------------- конвеєр генерації (двигун підмінений)
class FakeBackend:
    engine, model = "fake-engine", "fake-model"

    def __init__(self):
        self.generated, self.sim_calls = [], 0

    def generate(self, jobs, raws, log=print):
        for i, j in enumerate(jobs):
            synth(raws[i], 0.5 + 0.1 * j.k, 200 + j.seed)
            self.generated.append(j)

    def similarity(self, pairs):
        self.sim_calls += 1
        return {p["id"]: 0.9 for p in pairs}


class FakeAsr:
    def transcribe(self, paths):
        return {str(p): "Зроблю." for p in paths}


def record_approved(svc, *lids):
    for lid in lids:
        f = svc.add_take(CID, GID, lid, own_wav())["takes"][-1]["file"]
        svc.approve(CID, GID, lid, f)


def test_cer_and_style_and_norm():
    assert aigen.cer("Зроблю.", "зроблю") == 0.0
    assert aigen.cer("Так, так!", "Так так") == 0.0
    assert aigen.cer("абвг", "абдг") == 0.25
    assert aigen.cer("а", "яяяя") == 1.0 and aigen.cer("", "") == 0.0 and aigen.cer("", "x") == 1.0
    assert aigen.style_tag("слухняно-бадьоро") == "[cheerful]" and aigen.style_tag("") is None
    assert aigen.style_tag("без ключових слів") is None


def test_run_generates_all_variants_with_sidecars_and_skips_existing(svc, tmp_path):
    record_approved(svc, "peonyes1.wav", "peonyes2.wav", "peonyes3.wav")
    be = FakeBackend()
    res = aigen.run(svc, CID, GID, 3, backend=be, asr=FakeAsr(), only=["peonyes1", "peonwhat1.wav"], log=lambda *_: None)
    assert res["made"] == 6 and res["skipped"] == 0 and res["filled"] == 6
    files = sorted(p.name for p in AI_DIR.glob("*.wav"))
    assert files == [f"{s}.ai{k}.wav" for s in ("peonwhat1", "peonyes1") for k in (1, 2, 3)]
    meta = ai.read_sidecar(AI_DIR / "peonyes1.ai2.wav")
    assert set(ai.SIDECAR_KEYS) <= set(meta)
    assert meta["engine"] == "fake-engine" and meta["ai"] is True and meta["cer"] == 0.0 and meta["similarity"] == 0.9
    assert meta["style"] == "[cheerful]" and meta["text"] == "Зроблю." and meta["seed"] == 2
    assert all(r.startswith("peonyes") and "peonyes1." not in r for r in meta["ref_takes"])   # референс — інші репліки
    assert ai.read_sidecar(AI_DIR / "peonyes1.ai1.wav")["style"] is None                    # варіант 1 — без підказки
    # тексти двигуну: варіант із підказкою отримує тег, ЦІЛЬ для CER — чистий текст
    j2 = next(j for j in be.generated if j.stem == "peonyes1" and j.k == 2)
    assert j2.text == "[cheerful] Зроблю." and j2.plain == "Зроблю."
    # повторний запуск нічого не робить
    be2 = FakeBackend()
    again = aigen.run(svc, CID, GID, 3, backend=be2, asr=FakeAsr(), only=["peonyes1", "peonwhat1.wav"], log=lambda *_: None)
    assert again["made"] == 0 and again["skipped"] == 6 and again["filled"] == 0 and not be2.generated
    # файл гри / власні дублі не змінені; EQ не застосовано до збереженого файлу
    assert not (TMP_ROOT / "game-files/Units/orc/peon/peonwhat1.wav").exists()


def test_run_fills_missing_metrics_only(svc):
    record_approved(svc, "peonyes2.wav")
    be = FakeBackend()
    aigen.run(svc, CID, GID, 1, backend=be, asr=FakeAsr(), only=["peonyes1"], log=lambda *_: None)
    wav = AI_DIR / "peonyes1.ai1.wav"
    meta = ai.read_sidecar(wav)
    meta.update(cer=None, similarity=0.5)
    ai.write_sidecar(wav, meta)
    be2 = FakeBackend()
    res = aigen.run(svc, CID, GID, 1, backend=be2, asr=FakeAsr(), only=["peonyes1"], log=lambda *_: None)
    assert res["made"] == 0 and res["filled"] == 1
    m = ai.read_sidecar(wav)
    assert m["cer"] == 0.0 and m["similarity"] == 0.5                       # наявну схожість не перераховуємо


def test_run_requires_own_takes_and_never_uses_reference_audio(svc):
    with pytest.raises(StudioError, match="власних дублів"):
        aigen.run(svc, CID, GID, 1, backend=FakeBackend(), asr=FakeAsr(), only=["peonyes1"], log=lambda *_: None)
    record_approved(svc, "peonyes1.wav", "peonyes2.wav")
    be = FakeBackend()
    aigen.run(svc, CID, GID, 1, backend=be, asr=FakeAsr(), only=["peonyes1"], log=lambda *_: None)
    refs = be.generated[0].refs
    assert [r["text"] for r in refs] == ["З задоволенням."]                  # лише власний дубль іншої репліки
    assert all("reference" not in r["audio"].replace("ref-", "") for r in refs)


def test_run_skips_when_engine_gives_no_audio(svc):
    record_approved(svc, "peonyes2.wav")

    class Silent(FakeBackend):
        def generate(self, jobs, raws, log=print):
            pass

    logs = []
    res = aigen.run(svc, CID, GID, 1, backend=Silent(), asr=FakeAsr(), only=["peonyes1"], log=logs.append)
    assert res["made"] == 0 and any("двигун не дав звуку" in m for m in logs)


def test_postprocess_matches_original_loudness_without_eq(svc):
    record_approved(svc, "peonyes2.wav")
    jobs = aigen.plan(svc, CID, GID, 1, TMP_ROOT / "plan-tmp", only=["peonyes1"])
    raw = synth(TMP_ROOT / "plan-tmp/raw.wav", 0.9, 250)
    assert aigen.postprocess(svc, jobs[0], raw) and jobs[0].out.is_file()
    from studio import proc
    ref = svc.line(CID, GID, LID).ref_path
    assert abs(proc.mean_volume(jobs[0].out, []) - proc.mean_volume(ref, [proc.AUTO_TRIM])) < 1.5


def test_fish_paths_env_override(monkeypatch):
    monkeypatch.setenv("WC3_FISH_PY", "/x/py")
    assert aigen.fish_paths()["py"] == "/x/py"
    assert aigen._worker("fish_worker.py").endswith("tools/ai_engines/fish_worker.py")


def test_real_workers_report_failure(tmp_path):
    """_run_worker: ненульовий код робітника → StudioError; рядки JSON передаються в колбек."""
    script = tmp_path / "w.py"
    script.write_text("import json,sys\nprint(json.dumps({'id': 'a', 'similarity': 0.5}), flush=True)\n"
                      "sys.exit(int(json.load(open(sys.argv[1]))['rc']))\n")
    import sys
    got = []
    aigen._run_worker(sys.executable, str(script), {"rc": 0}, got.append)
    assert got == [{"id": "a", "similarity": 0.5}]
    with pytest.raises(StudioError):
        aigen._run_worker(sys.executable, str(script), {"rc": 3}, got.append)


def test_fish_backend_builds_job_spec(monkeypatch, tmp_path):
    seen = {}
    monkeypatch.setattr(aigen, "_run_worker", lambda py, worker, spec, cb: seen.update(worker=worker, spec=spec)
                        or cb({"id": "f.wav", "similarity": 0.7}))
    be = aigen.FishBackend()
    job = aigen.Job(CID, GID, LID, "peonyes1", 1, "[x] Зроблю.", "Зроблю.", 7, 0.7, 0.7, "[x]",
                    refs=[{"take": "t", "audio": "/a.wav", "text": "Так."}], out=tmp_path / "o.wav")
    be.generate([job], {0: tmp_path / "raw.wav"}, lambda *_: None)
    assert seen["spec"]["jobs"][0]["max_new"] == 512 and seen["spec"]["jobs"][0]["seed"] == 7 and seen["spec"]["jobs"][0]["refs"] == [{"audio": "/a.wav", "text": "Так."}]
    assert be.similarity([{"id": "f.wav", "wav": "w", "refs": ["r"]}]) == {"f.wav": 0.7}
    assert be.similarity([]) == {}


def test_cli_main_reads_state_without_saving(svc, monkeypatch, capsys):
    from studio import core
    record_approved(svc, "peonyes2.wav")
    state = (TMP_ROOT / "data/studio/units-orc.json").read_bytes()
    monkeypatch.setattr(aigen, "FishBackend", FakeBackend)
    monkeypatch.setattr(aigen, "WhisperCer", FakeAsr)
    saved = core.Store.save
    try:
        assert aigen.main(["--variants", "2", "--only", "peonyes1"]) == 0
    finally:
        core.Store.save = saved
    assert "нових 2" in capsys.readouterr().out
    assert (TMP_ROOT / "data/studio/units-orc.json").read_bytes() == state      # стан студії не змінено
    assert (AI_DIR / "peonyes1.ai2.wav").exists()


def test_whisper_cer_backend_uses_ukrainian(monkeypatch, tmp_path):
    import sys
    import types
    calls = []
    fake = types.SimpleNamespace(transcribe=lambda p, **kw: calls.append(kw) or {"text": " Зроблю. "})
    monkeypatch.setitem(sys.modules, "mlx_whisper", fake)
    w = tmp_path / "a.wav"
    assert aigen.WhisperCer().transcribe([w]) == {str(w): "Зроблю."} and calls[0]["language"] == "uk"


def test_runaway_generation_rejected_and_retried_with_new_seed(svc):
    record_approved(svc, "peonyes2.wav")

    class Runaway(FakeBackend):
        def generate(self, jobs, raws, log=print):
            for i, j in enumerate(jobs):
                synth(raws[i], 12 if j.seed == 1 else 0.6, 200)          # seed 1 «заблукав» (12 с замість ~1 с)
                self.generated.append(j)

    be, logs = Runaway(), []
    res = aigen.run(svc, CID, GID, 1, backend=be, asr=FakeAsr(), only=["peonyes1"], log=logs.append)
    assert res["made"] == 1 and any("надто довго" in m for m in logs)
    meta = ai.read_sidecar(AI_DIR / "peonyes1.ai1.wav")
    assert meta["seed"] == 1001 and meta["dur"] < 2                          # повтор із seed + 1000
    assert [j.seed for j in be.generated] == [1, 1001]
