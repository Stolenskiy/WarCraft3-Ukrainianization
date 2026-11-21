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


def test_whisper_hallucination_is_not_text(svc):
    ln = svc.line(CID, GID, "peondeath.wav")
    assert ln.no_speech and "без розбірливих слів" in ln.ru


def test_real_data_parses():
    """Справжні аркуші voice bible і транскрипти з репозиторію читаються (без аудіо)."""
    from conftest import REPO
    from studio.catalog import parse_bible
    for md in (REPO / "docs/voice-bible").glob("*.md"):
        if md.name != "README.md":
            units = parse_bible(md)
            assert units and any(u["rows"] for u in units.values()), md.name
    for f in (REPO / "data").glob("transcripts-*.json"):
        assert all("text" in v for v in json.loads(f.read_text(encoding="utf-8")).values()), f.name


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


def test_english_only_unit_works_without_russian_pack(svc):
    assert "hellscream" in [g["id"] for g in svc.catalogs_json()[0]["groups"]]
    ln = svc.line(CID, "hellscream", "gromyes1.wav")
    j = svc.line_json(CID, "hellscream", ln)
    assert not j["has_ru"] and j["has_en"]
    assert svc.audio_path("ref", CID, "hellscream", "gromyes1.wav").parts[-5] == "reference-en"
    assert svc.add_take(CID, "hellscream", "gromyes1.wav", wav_bytes())["takes"]


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


def test_build_refs_unmangles_casc_names(tmp_path):
    import build_refs
    raw, out = tmp_path / "raw", tmp_path / "out"
    for n in ("orc/heheadhunteryes1.wav", "orc/grunt/gruntyes1.wav", "orc/swhitetaurenwhat1.wav",
              "orc/taurenwhat1.wav"):
        (raw / n).parent.mkdir(parents=True, exist_ok=True)
        (raw / n).write_bytes(n.encode())
    done, missing = build_refs.layout(raw, out, ["orc/headhunter/headhunteryes1.wav", "orc/grunt/gruntyes1.wav",
                                                 "orc/tauren/taurenwhat1.wav", "orc/peon/peonyes1.wav"])
    assert (done, missing) == (3, 1)
    assert (out / "orc/headhunter/headhunteryes1.wav").read_bytes() == b"orc/heheadhunteryes1.wav"
    assert (out / "orc/tauren/taurenwhat1.wav").read_bytes() == b"orc/taurenwhat1.wav"   # не swhitetauren


def test_api_rejects_foreign_host_origin_and_bad_length(api):
    assert api("/api/catalogs", headers={"Host": "attacker.example"})[0] == 403          # DNS-rebinding
    body = {"cid": CID, "gid": GID, "lid": LID, "text": "x"}
    assert api("/api/text", body, headers={"Origin": "http://attacker.example"})[0] == 403
    assert api("/api/text", body, headers={"Content-Length": "-1"})[0] in (400, 413)
    assert api("/api/text", {"cid": CID, "gid": GID, "lid": LID, "text": 1})[0] == 400


def test_non_wav_upload_rejected_before_ffmpeg(svc):
    from studio.core import StudioError
    with pytest.raises(StudioError, match="WAV"):
        svc.add_take(CID, GID, LID, b"#EXTM3U\n#EXT-X-VERSION:3\nfile:///etc/passwd\n")


def test_corrupt_state_falls_back_to_backup(clean_root):
    from studio import core
    s = core.Service()
    s.set_text(CID, GID, LID, "перший")
    s.set_text(CID, GID, LID, "другий")                    # .bak = стан із «перший»
    st = clean_root / "data/studio/units-orc.json"
    st.write_text("{зіпсовано", encoding="utf-8")
    s2 = core.Service()
    assert s2.line_json(CID, GID, s2.line(CID, GID, LID))["ua"] == "перший"
    st.with_suffix(".json.bak").unlink()
    with pytest.raises(core.StudioError):
        core.Service().line(CID, GID, LID)
