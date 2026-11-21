"""Ядро студії + HTTP API (без браузера). Запуск: make test"""
import json
import threading
import urllib.error
import urllib.request

import pytest
from conftest import TMP_ROOT, synth
from studio import eq
from studio.core import StudioError

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


# ---------------------------------------------------------------- ручне обрізання (trim)
def _take2s(svc):
    r = svc.add_take(CID, GID, LID, synth(TMP_ROOT / "two.wav", 2.0).read_bytes())
    return r["takes"][-1]["file"]


def test_set_trim_validation_and_export(svc):
    from studio.catalog import duration
    from studio.core import StudioError
    f = _take2s(svc)
    game = TMP_ROOT / "game-files/Units/orc/peon/peonyes1.wav"
    for bad in ((-0.1, 1.0), (1.0, 1.0), (1.5, 0.5), (0.0, 2.5), (0.5, 0.6), ("a", 1.0), (0.5, None)):
        with pytest.raises(StudioError):
            svc.set_trim(CID, GID, LID, f, *bad)
    assert svc.set_trim(CID, GID, LID, f, 0.5, 1.5)["takes"][-1]["trim"] == {"start": 0.5, "end": 1.5}
    assert not game.exists()                             # незатверджений — копії немає
    svc.approve(CID, GID, LID, f, trim=False)
    assert 0.95 < duration(game) < 1.05, duration(game)
    assert duration(TMP_ROOT / "audio/self-recorded" / CID / GID / f) > 1.9   # оригінал недоторканий
    hist = [h["action"] for h in svc.line_json(CID, GID, svc.line(CID, GID, LID))["history"]]
    assert any(a.startswith("обрізано дубль") and "0.50–1.50 с" in a for a in hist)


def test_set_trim_reexports_approved_and_clears(svc):
    from studio.catalog import duration
    f = _take2s(svc)
    game = TMP_ROOT / "game-files/Units/orc/peon/peonyes1.wav"
    svc.approve(CID, GID, LID, f, trim=False)
    assert duration(game) > 1.9
    r = svc.set_trim(CID, GID, LID, f, 0.5, 1.5, auto_trim=False)   # одразу перекопіювалось
    assert 0.95 < duration(game) < 1.05
    assert r["approved"] == f
    r = svc.set_trim(CID, GID, LID, f, None, None)
    assert r["takes"][-1]["trim"] is None and duration(game) > 1.9
    assert r["history"][-1]["action"].startswith("скинуто обрізання")
    n = len(r["history"])
    assert len(svc.set_trim(CID, GID, LID, f, None, None)["history"]) == n   # повторне скидання — без запису


def test_trim_survives_reload_and_applies_before_auto_trim(svc):
    from studio import core
    f = _take2s(svc)
    svc.set_trim(CID, GID, LID, f, 0.5, 1.5)
    t = core.Service().line_json(CID, GID, svc.line(CID, GID, LID))["takes"][-1]
    assert t["trim"] == {"start": 0.5, "end": 1.5}
    flt = svc._export_filters(CID, GID, svc.store(CID).entry(GID, LID)["takes"][-1], True)
    assert flt[0].startswith("atrim=start=0.500:end=1.500,asetpts=PTS-STARTPTS") and flt[1] == core.AUTO_TRIM


def test_api_trim(api):
    code, ln = api(f"/api/take?cid={CID}&gid={GID}&lid={LID}", raw=synth(TMP_ROOT / "two.wav", 2.0).read_bytes())
    f = ln["takes"][-1]["file"]
    code, ln = api("/api/trim", {"cid": CID, "gid": GID, "lid": LID, "file": f, "start": 0.2, "end": 1.2})
    assert code == 200 and ln["takes"][-1]["trim"] == {"start": 0.2, "end": 1.2}
    code, err = api("/api/trim", {"cid": CID, "gid": GID, "lid": LID, "file": f, "start": 1.2, "end": 0.2})
    assert code == 400 and "error" in err
    code, ln = api("/api/trim", {"cid": CID, "gid": GID, "lid": LID, "file": f, "start": None, "end": None})
    assert code == 200 and ln["takes"][-1]["trim"] is None


def test_set_trim_rejects_deleted_missing_and_unknown(svc):
    from studio.core import StudioError
    f = _take2s(svc)
    with pytest.raises(StudioError):
        svc.set_trim(CID, GID, LID, "nope.take9.wav", 0.1, 1.0)
    p = svc.take_path(CID, GID, svc.store(CID).entry(GID, LID)["takes"][-1])
    p.rename(p.with_suffix(".bak"))                      # файл зник
    with pytest.raises(StudioError):
        svc.set_trim(CID, GID, LID, f, 0.1, 1.0)
    p.with_suffix(".bak").rename(p)
    svc.delete(CID, GID, LID, f)
    with pytest.raises(StudioError):
        svc.set_trim(CID, GID, LID, f, 0.1, 1.0)
    assert svc.set_trim(CID, GID, LID, f, None, None)["takes"][-1]["trim"] is None


# ---------------------------------------------------------------- вміст копії для гри після обрізання
def _segments_wav(path):
    """2 с: 0–0.5 тиша, 0.5–1.0 тон 440 Гц, 1.0–1.5 тон 880 Гц, 1.5–2.0 тиша (stdlib, 22050 Hz mono s16)."""
    import math
    import struct
    import wave
    sr, out = 22050, []
    for i in range(2 * sr):
        t = i / sr
        f = 440 if 0.5 <= t < 1.0 else 880 if 1.0 <= t < 1.5 else 0
        out.append(int(12000 * math.sin(2 * math.pi * f * t)) if f else 0)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(struct.pack(f"<{len(out)}h", *out))
    return path


def _read_game():
    import struct
    import wave
    with wave.open(str(TMP_ROOT / "game-files/Units/orc/peon/peonyes1.wav")) as w:
        assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (22050, 1, 2)
        n = w.getnframes()
        return n / 22050, struct.unpack(f"<{n}h", w.readframes(n))


def _zcr_hz(samples):
    """Частота за перетинами нуля (для чистого тону)."""
    z = sum(1 for a, b in zip(samples, samples[1:], strict=False) if (a < 0) != (b < 0))
    return z / 2 / (len(samples) / 22050)


def test_game_file_content_matches_trim(svc):
    f = svc.add_take(CID, GID, LID, _segments_wav(TMP_ROOT / "seg.wav").read_bytes())["takes"][-1]["file"]
    svc.set_trim(CID, GID, LID, f, 0.6, 1.4)
    svc.approve(CID, GID, LID, f, trim=False)
    d, s = _read_game()
    assert abs(d - 0.8) < 0.02, d
    h = len(s) // 2
    assert abs(_zcr_hz(s[:h]) - 440) < 40 and abs(_zcr_hz(s[h:]) - 880) < 80   # 0.6–1.0 → 440, 1.0–1.4 → 880

    r = svc.set_trim(CID, GID, LID, f, 0.2, 1.8, auto_trim=False)      # зміна trim затвердженого → перезапис
    assert abs(_read_game()[0] - 1.6) < 0.02 and r["approved"] == f

    svc.set_trim(CID, GID, LID, f, 0.2, 1.8, auto_trim=True)           # тиша в межах обрізання → авто-обрізання
    d, s = _read_game()
    assert 0.95 < d < 1.3, d          # тон 1.0 с + запас авто-обрізання, а не 1.6 с
    n = len(s)
    assert _zcr_hz(s[n * 15 // 100: n * 35 // 100]) < 600 < _zcr_hz(s[n * 65 // 100: n * 85 // 100])

    svc.set_trim(CID, GID, LID, f, None, None, auto_trim=False)        # скидання → повна довжина
    assert abs(_read_game()[0] - 2.0) < 0.02


def test_failed_export_does_not_approve_or_keep_trim(svc):
    """trim у самій тиші + авто-обрізання → порожньо: помилка, а не сира копія; стан не змінюється."""
    f = svc.add_take(CID, GID, LID, _segments_wav(TMP_ROOT / "seg.wav").read_bytes())["takes"][-1]["file"]
    svc.set_trim(CID, GID, LID, f, 1.6, 1.95)                          # лише тиша
    with pytest.raises(StudioError, match="замало звуку"):
        svc.approve(CID, GID, LID, f, trim=True)
    line = svc.group_json(CID, GID)["lines"][0]
    assert line["approved"] is None and not (TMP_ROOT / "game-files/Units/orc/peon/peonyes1.wav").exists()

    svc.set_trim(CID, GID, LID, f, 0.6, 1.4)
    svc.approve(CID, GID, LID, f, trim=True)
    n_hist = len(svc.group_json(CID, GID)["lines"][0]["history"])
    with pytest.raises(StudioError):                                   # зміна trim затвердженого → у тишу
        svc.set_trim(CID, GID, LID, f, 1.6, 1.95, auto_trim=True)
    line = svc.group_json(CID, GID)["lines"][0]
    assert line["takes"][-1]["trim"] == {"start": 0.6, "end": 1.4}     # відкат
    assert len(line["history"]) == n_hist                               # без запису в журнал
    assert 0.7 < _read_game()[0] < 0.95                                 # файл гри — попередній


def test_trim_autotrim_eq_chain_and_reexport_keep_trim(svc):
    f = svc.add_take(CID, GID, LID, _segments_wav(TMP_ROOT / "seg.wav").read_bytes())["takes"][-1]["file"]
    svc.set_trim(CID, GID, LID, f, 0.6, 1.4)
    take = svc.store(CID).entry(GID, LID)["takes"][-1]
    chain = svc._export_filters(CID, GID, take, True)
    assert chain[0].startswith("atrim=start=0.600:end=1.400") and chain[1].startswith("silenceremove")
    assert chain[2:] == eq.to_ffmpeg(svc.eq.presets["orc-peon"])        # EQ персонажа — останнім
    svc.approve(CID, GID, LID, f, trim=False)
    assert abs(_read_game()[0] - 0.8) < 0.02
    (TMP_ROOT / "game-files/Units/orc/peon/peonyes1.wav").write_bytes(b"stale")
    assert svc.reexport_group(CID, GID, trim=False)["done"] == [LID]    # EQ-перезапис поважає trim дубля
    assert abs(_read_game()[0] - 0.8) < 0.02


def test_direction_is_per_phrase():
    from studio.catalog import direction_for
    d = "слухняно-бадьоро; «Так, так!» — квапливо, як школяр"
    assert direction_for(d, "Добре.") == "слухняно-бадьоро"
    assert direction_for(d, "Так, так!") == d
    d = "хоробрість мимоволі: «Бий їх!» — зі щирим запалом; «Спробуємо.» — зі зітхом"
    assert direction_for(d, "У-ху!") == "хоробрість мимоволі"
    assert direction_for(d, "Спробуємо.") == "хоробрість мимоволі; «Спробуємо.» — зі зітхом"
    assert direction_for("«А» — тихо", "Б") == "«А» — тихо"            # нічого не лишилось → увесь напрям


# ---------------------------------------------------------------- перевантаження (clipping)
def _tone_wav(amp, sec=0.8):
    import subprocess
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                        f"sine=frequency=300:sample_rate=22050:duration={sec}", "-af", f"volume={amp}",
                        "-ac", "1", "-sample_fmt", "s16", "-f", "wav", "-"], capture_output=True, check=True)
    return r.stdout


def test_wav_peak_detects_clipping(tmp_path):
    from studio.core import wav_peak
    loud, quiet = tmp_path / "loud.wav", tmp_path / "quiet.wav"
    loud.write_bytes(_tone_wav(16))        # синус ×2 від повної шкали → зрізаний на повній шкалі
    quiet.write_bytes(_tone_wav(4))
    pk, n = wav_peak(loud)
    assert pk > -0.2 and n > 10
    pk, n = wav_peak(quiet)
    assert -7 < pk < -5 and n == 0


def test_add_take_flags_clipped_and_normal(svc):
    r = svc.add_take(CID, GID, LID, _tone_wav(16))
    t = r["takes"][-1]
    assert t["clipped"] is True and t["peak_db"] > -0.2
    r = svc.add_take(CID, GID, LID, _tone_wav(4))
    t = r["takes"][-1]
    assert t["clipped"] is False and -7 < t["peak_db"] < -5


def test_old_takes_without_peak_fields_ok(svc):
    r = svc.add_take(CID, GID, LID, wav_bytes())
    for t in svc.store(CID).entry(GID, LID)["takes"]:
        t.pop("peak_db", None), t.pop("clipped", None)
    t = svc.group_json(CID, GID)["lines"][0]["takes"][0]
    assert t["peak_db"] is None and t["clipped"] is False and r["takes"]


def test_api_take_reports_clipping(api):
    code, ln = api(f"/api/take?cid={CID}&gid={GID}&lid={LID}", raw=_tone_wav(16))
    assert code == 200 and ln["takes"][-1]["clipped"] is True
