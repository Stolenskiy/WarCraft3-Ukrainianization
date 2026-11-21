"""Ядро студії + HTTP API (без браузера). Запуск: make test"""
import json
import threading
import urllib.error
import urllib.request

import pytest
from conftest import TMP_ROOT, synth

CID, GID, LID = "units-orc", "peon", "peonyes1.wav"


def wav_bytes(sec=0.8):
    return synth(TMP_ROOT / "tmp-upload.wav", sec).read_bytes()


# ---------------------------------------------------------------- каталоги
def test_catalogs_cover_races_and_units(svc):
    cats = {c["id"]: c for c in svc.catalogs_json()}
    assert {"units-orc", "units-human"} <= set(cats)
    orc = [g["id"] for g in cats["units-orc"]["groups"]]
    assert orc[0] == "peon" and "grunt" in orc
    sections = {g["id"]: g["section"] for g in cats["units-orc"]["groups"]}
    assert sections["thrall"] == "Кампанія" and sections["grunt"].startswith("Melee")


def test_lines_have_russian_text_and_ukrainian_hint(svc):
    lines = {ln.id: ln for ln in svc.lines(CID, GID)}
    assert lines[LID].ru == "Сделаю." and lines[LID].ua_hint == "Зроблю."
    assert lines["peonwhat4.wav"].ua_hint == "Чого треба, хазяїне?"
    assert lines[LID].game_rel == "Units/orc/peon/peonyes1.wav"
    assert lines[LID].direction


def test_every_group_loads(svc):
    for c in svc.catalogs_json():
        for g in c["groups"]:
            assert svc.lines(c["id"], g["id"]), g["id"]


def test_english_original_optional(svc):
    peon = svc.line_json(CID, GID, svc.line(CID, GID, LID))
    grunt = svc.line_json(CID, "grunt", svc.line(CID, "grunt", "gruntyes1.wav"))
    assert peon["has_en"] and not grunt["has_en"]
    assert svc.audio_path("ref-en", CID, GID, LID).parent.parent.parent.parent.name == "reference-en"
    from studio.core import StudioError
    with pytest.raises(StudioError):
        svc.audio_path("ref-en", CID, "grunt", "gruntyes1.wav")


# ---------------------------------------------------------------- дублі
def test_take_lifecycle_invariants(svc):
    r = svc.add_take(CID, GID, LID, wav_bytes())
    r = svc.add_take(CID, GID, LID, wav_bytes())
    files = [t["file"] for t in r["takes"]]
    assert files == ["peonyes1.take1.wav", "peonyes1.take2.wav"]
    game = TMP_ROOT / "game-files/Units/orc/peon/peonyes1.wav"

    r = svc.approve(CID, GID, LID, files[0])
    assert r["approved"] == files[0] and game.exists()
    r = svc.approve(CID, GID, LID, files[1])                 # змінити рішення
    assert r["approved"] == files[1]

    r = svc.delete(CID, GID, LID, files[1])                  # видалити обраний → вибір знято
    assert r["approved"] is None and not game.exists()
    assert (TMP_ROOT / "audio/self-recorded/units-orc/peon/_deleted" / files[1]).exists()

    r = svc.add_take(CID, GID, LID, wav_bytes())             # номер не перезаписує видалений
    assert r["takes"][-1]["file"] == "peonyes1.take3.wav"

    r = svc.restore(CID, GID, LID, files[1])
    assert not next(t for t in r["takes"] if t["file"] == files[1])["deleted"]

    r = svc.unapprove(CID, GID, LID)
    assert r["approved"] is None
    assert len(r["history"]) >= 7


def test_cannot_approve_deleted(svc):
    r = svc.add_take(CID, GID, LID, wav_bytes())
    f = r["takes"][0]["file"]
    svc.delete(CID, GID, LID, f)
    from studio.core import StudioError
    with pytest.raises(StudioError):
        svc.approve(CID, GID, LID, f)


def test_too_short_take_rejected(svc):
    from studio.core import StudioError
    with pytest.raises(StudioError):
        svc.add_take(CID, GID, LID, wav_bytes(0.1))


def test_trim_removes_silence(svc):
    import subprocess
    p = TMP_ROOT / "pad.wav"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    "sine=frequency=300:sample_rate=22050:duration=0.6", "-af", "adelay=1000,apad=pad_dur=1",
                    "-ac", "1", "-sample_fmt", "s16", str(p)], check=True)
    r = svc.add_take(CID, GID, LID, p.read_bytes())
    svc.approve(CID, GID, LID, r["takes"][0]["file"], trim=True)
    from studio.catalog import duration
    d = duration(TMP_ROOT / "game-files/Units/orc/peon/peonyes1.wav")
    assert 0.6 <= d < 1.2, d


def test_text_edit_persists(svc):
    svc.set_text(CID, GID, LID, "  Зроблю, хазяїне. ")
    from studio import core
    again = core.Service().line_json(CID, GID, core.Service().line(CID, GID, LID))
    assert again["ua"] == "Зроблю, хазяїне." and again["ua_custom"]


def test_orphan_files_adopted(clean_root):
    synth(clean_root / "audio/self-recorded/units-orc/peon/peonyes2.take7.wav")
    from studio import core
    s = core.Service()
    e = s.line_json(CID, GID, s.line(CID, GID, "peonyes2.wav"))
    assert [t["file"] for t in e["takes"]] == ["peonyes2.take7.wav"]
    assert s.add_take(CID, GID, "peonyes2.wav", wav_bytes())["takes"][-1]["file"] == "peonyes2.take8.wav"


def test_legacy_v2_migration(clean_root):
    synth(clean_root / "audio/self-recorded/peon/peonyes1.take5.wav")
    (clean_root / "data/record-studio-orc.json").write_text(json.dumps({"version": 2, "units": {"peon": {
        LID: {"ua_text": None, "approved": None, "history": [],
              "takes": [{"file": "peonyes1.take5.wav", "created": "2026-11-21T22:00:00", "deleted": None}]}}}}))
    from studio import core
    s = core.Service()
    e = s.line_json(CID, GID, s.line(CID, GID, LID))
    assert e["takes"][0]["file"] == "peonyes1.take5.wav" and e["takes"][0]["exists"]
    assert not (clean_root / "audio/self-recorded/peon").exists()


# ---------------------------------------------------------------- HTTP API
@pytest.fixture
def api(svc):
    from studio.server import serve
    httpd = serve(0, open_browser=False, svc=svc)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"

    def call(path, body=None, headers=None, raw=None):
        h = {"X-Studio": "1", **(headers or {})}
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        req = urllib.request.Request(base + path, data=data, headers=h, method="POST" if data is not None else "GET")
        try:
            with urllib.request.urlopen(req) as r:
                ct = r.headers.get("Content-Type", "")
                return r.status, (json.loads(r.read()) if "json" in ct else r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())
    yield call
    httpd.shutdown()


def test_api_flow(api):
    code, cats = api("/api/catalogs")
    assert code == 200 and cats[0]["id"] == CID
    code, g = api(f"/api/group/{CID}/{GID}")
    assert code == 200 and g["lines"][0]["id"]
    code, ln = api(f"/api/take?cid={CID}&gid={GID}&lid={LID}", raw=wav_bytes())
    assert code == 200 and ln["takes"][0]["file"] == "peonyes1.take1.wav"
    code, ln = api("/api/approve", {"cid": CID, "gid": GID, "lid": LID, "file": "peonyes1.take1.wav"})
    assert code == 200 and ln["approved"]
    for kind, name in (("ref", LID), ("ref-en", LID), ("take", "peonyes1.take1.wav"), ("game", LID)):
        code, body = api(f"/audio/{kind}/{CID}/{GID}/{name}")
        assert code == 200 and body[:4] == b"RIFF", kind


def test_api_security(api):
    code, _ = api("/api/text", {"cid": CID, "gid": GID, "lid": LID, "text": "x"}, headers={"X-Studio": "0"})
    assert code == 403
    code, _ = api(f"/audio/ref/{CID}/{GID}/..%2F..%2F..%2Fetc%2Fpasswd")
    assert code == 404
    code, _ = api(f"/audio/take/{CID}/{GID}/..%2Fpeonyes1.wav")
    assert code == 404
    code, _ = api("/api/approve", {"cid": CID, "gid": "nope", "lid": LID, "file": "x"})
    assert code == 400


def test_legacy_v1_migration(clean_root):
    synth(clean_root / "audio/self-recorded/peon/peonyes2.take1.wav")
    (clean_root / "data/record-session-peon.json").write_text(json.dumps(
        {"PeonYes2.wav": {"takes": ["peonyes2.take1.wav"], "approved": None}}))
    from studio import core
    s = core.Service()
    e = s.line_json(CID, GID, s.line(CID, GID, "peonyes2.wav"))
    assert [t["file"] for t in e["takes"]] == ["peonyes2.take1.wav"] and e["takes"][0]["exists"]


def test_errors_are_explicit(svc):
    from studio.core import StudioError
    for call in (lambda: svc.lines("units-nope", GID),
                 lambda: svc.line(CID, GID, "nope.wav"),
                 lambda: svc.approve(CID, GID, LID, "peonyes1.take99.wav"),
                 lambda: svc.restore(CID, GID, LID, "peonyes1.take99.wav")):
        with pytest.raises(StudioError):
            call()
    f = svc.add_take(CID, GID, LID, wav_bytes())["takes"][0]["file"]
    (TMP_ROOT / "audio/self-recorded/units-orc/peon" / f).unlink()      # файл зник з диска
    with pytest.raises(StudioError):
        svc.approve(CID, GID, LID, f)


def test_api_bad_requests(api):
    assert api("/api/approve", {"cid": CID})[0] == 400                    # бракує полів
    assert api("/api/nope", {})[0] == 404
    assert api("/nope")[0] == 404
    assert api("/static/../core.py")[0] == 404
    assert api("/api/take?cid=units-orc&gid=peon&lid=peonyes1.wav", raw=b"not a wav")[0] == 400
