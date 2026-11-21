"""Обробка звуку для гри: налаштування, ланцюжок, темп, гучність, шумоговорення, «Як у грі» (proc.py + core + API)."""
import json
import math
import random
import struct
import wave

import pytest
from conftest import TMP_ROOT
from studio import core, eq, proc
from studio.core import StudioError
from test_studio_core import CID, GID, LID, _read_game, _segments_wav, _zcr_hz, api, wav_bytes  # noqa: F401

GAME = TMP_ROOT / "game-files/Units/orc/peon/peonyes1.wav"


def _write(path, samples):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(22050)
        w.writeframes(struct.pack(f"<{len(samples)}h", *[max(-32768, min(32767, int(x))) for x in samples]))
    return path


def _rms_db(s):
    return 10 * math.log10(sum(x * x for x in s) / len(s) / 32768 ** 2 + 1e-12)


def _read(path):
    with wave.open(str(path)) as w:
        return list(struct.unpack(f"<{w.getnframes()}h", w.readframes(w.getnframes())))


def _tone(sec=0.8, amp=0.1, spike=False, noise=0.0):
    rnd, out = random.Random(1), []
    for i in range(int(sec * 22050)):
        t = i / 22050
        v = amp * math.sin(2 * math.pi * 440 * t) if 0.25 <= t < sec - 0.25 or not noise else 0.0
        if spike and 0.4 <= t < 0.42:
            v += 0.5
        out.append(32767 * v + (rnd.gauss(0, noise * 32767) if noise else 0))
    return out


def _add(svc, samples):
    r = svc.add_take(CID, GID, LID, _write(TMP_ROOT / "synth.wav", samples).read_bytes())
    return r["takes"][-1]["file"]


def _take(svc, f):
    return next(t for t in svc.store(CID).entry(GID, LID)["takes"] if t["file"] == f)


# ---------------------------------------------------------------- налаштування
def test_settings_default_persist_and_validation(svc):
    assert svc.get_settings() == {"auto_trim": True, "denoise": False, "loudness": True}
    assert svc.set_settings({"denoise": True}) == {"auto_trim": True, "denoise": True, "loudness": True}
    assert json.loads((TMP_ROOT / "data/studio/settings.json").read_text())["denoise"] is True
    assert core.Service().get_settings()["denoise"] is True              # новий сервіс бачить збережене
    for bad in ({"nope": True}, {"denoise": "yes"}, {"denoise": 1}, []):
        with pytest.raises(StudioError):
            svc.set_settings(bad)
    (TMP_ROOT / "data/studio/settings.json").write_text("{зіпсовано")
    assert svc.get_settings()["auto_trim"] is True                       # зіпсований файл → типові


def test_legacy_trim_param_overrides_setting(svc):
    f = svc.add_take(CID, GID, LID, _segments_wav(TMP_ROOT / "seg.wav").read_bytes())["takes"][-1]["file"]
    svc.set_settings({"auto_trim": False})
    svc.approve(CID, GID, LID, f)                                         # за налаштуванням — без обрізання
    assert abs(_read_game()[0] - 2.0) < 0.02
    svc.approve(CID, GID, LID, f, trim=True)                              # застарілий override
    assert _read_game()[0] < 1.4
    svc.set_settings({"auto_trim": True})
    svc.approve(CID, GID, LID, f)
    assert _read_game()[0] < 1.4
    svc.approve(CID, GID, LID, f, trim=False)
    assert abs(_read_game()[0] - 2.0) < 0.02


# ---------------------------------------------------------------- ланцюжок
def test_chain_order_with_everything_on(svc):
    f = _add(svc, _tone(2.0))
    svc.set_trim(CID, GID, LID, f, 0.3, 1.8)
    svc.set_tempo(CID, GID, LID, f, 1.25)
    svc.set_settings({"auto_trim": True, "denoise": True, "loudness": True})
    ln, t = svc.line(CID, GID, LID), _take(svc, f)
    chain = svc._export_filters(CID, GID, t, None, ln)
    eqf = eq.to_ffmpeg(svc.eq.effective(CID, GID))
    assert eqf
    assert chain[:-2] == [chain[0], core.AUTO_TRIM, *proc.DENOISE, "atempo=1.2500", *eqf]
    assert chain[0].startswith("atrim=start=0.300:end=1.800")
    assert chain[-2].startswith("volume=") and chain[-2].endswith("dB") and chain[-1] == proc.LIMITER
    off = svc._export_filters(CID, GID, t, False, ln, {"auto_trim": False, "denoise": False, "loudness": False})
    assert off == [chain[0], "atempo=1.2500", *eqf]                       # усе вимкнено → лише обрізання, темп, EQ


# ---------------------------------------------------------------- темп
def test_tempo_changes_duration_not_pitch(svc):
    f = svc.add_take(CID, GID, LID, _segments_wav(TMP_ROOT / "seg.wav").read_bytes())["takes"][-1]["file"]
    svc.set_trim(CID, GID, LID, f, 0.5, 1.5)
    svc.approve(CID, GID, LID, f, trim=False)
    d0, s0 = _read_game()
    assert abs(d0 - 1.0) < 0.02
    r = svc.set_tempo(CID, GID, LID, f, 1.25)                             # затверджений → одразу перезапис
    assert r["takes"][-1]["tempo"] == 1.25
    d, s = _read_game()
    assert abs(d - 1.0 / 1.25) < 0.03, d
    h = len(s) // 2
    for a, b in ((_zcr_hz(s0[:len(s0) // 2]), _zcr_hz(s[:h])), (_zcr_hz(s0[len(s0) // 2:]), _zcr_hz(s[h:]))):
        assert abs(b - a) / a < 0.10, (a, b)                              # висота та сама ±10 %
    assert svc.set_tempo(CID, GID, LID, f, 1.0)["takes"][-1]["tempo"] == 1.0
    assert abs(_read_game()[0] - 1.0) < 0.02
    assert "tempo" not in _take(svc, f)


def test_set_tempo_validation_rollback_and_log(svc):
    f = _add(svc, _tone(0.3))
    for bad in (0.79, 1.31, "x", float("nan"), [1]):
        with pytest.raises(StudioError):
            svc.set_tempo(CID, GID, LID, f, bad)
    with pytest.raises(StudioError):
        svc.set_tempo(CID, GID, LID, "nope.take9.wav", 1.1)
    svc.approve(CID, GID, LID, f, trim=False)
    assert svc.set_tempo(CID, GID, LID, f, 1.1)["takes"][-1]["tempo"] == 1.1
    with pytest.raises(StudioError):                                      # 0.3 с / 1.3 < 0.25 с → відкат
        svc.set_tempo(CID, GID, LID, f, 1.3)
    assert svc.group_json(CID, GID)["lines"][0]["takes"][-1]["tempo"] == 1.1
    hist = svc.line_json(CID, GID, svc.line(CID, GID, LID))["history"]
    assert [h["action"] for h in hist if "темп" in h["action"]] == ["темп дубля 1: ×1.10"]
    n = len(hist)
    assert len(svc.set_tempo(CID, GID, LID, f, None)["history"]) == n + 1
    assert len(svc.set_tempo(CID, GID, LID, f, None)["history"]) == n + 1  # повторне скидання — без запису
    svc.delete(CID, GID, LID, f)
    with pytest.raises(StudioError):
        svc.set_tempo(CID, GID, LID, f, 1.2)


# ---------------------------------------------------------------- гучність
def test_loudness_matches_reference_and_never_clips(svc):
    ref = _read(svc.line(CID, GID, LID).ref_path)
    ref_db = _rms_db(ref)
    f = _add(svc, [x * 10 ** (-12 / 20) for x in ref])      # дубль на 12 дБ тихіше за оригінал
    svc.approve(CID, GID, LID, f, trim=False)
    s = _read(GAME)
    assert abs(_rms_db(s) - ref_db) < 1.5, (_rms_db(s), ref_db)
    assert max(abs(x) for x in s) / 32768 <= 10 ** (-0.2 / 20)

    svc.set_settings({"loudness": False})                                 # вимкнено → гучність дубля як є
    svc.approve(CID, GID, LID, f, trim=False)
    assert _rms_db(_read(GAME)) < ref_db - 10

    svc.set_settings({"loudness": True})
    g = _add(svc, _tone(0.8, amp=0.01, spike=True))                       # +18 дБ зробило б з піку кліп → лімітер
    svc.approve(CID, GID, LID, g, trim=False)
    peak = max(abs(x) for x in _read(GAME)) / 32768
    assert 0.9 < peak <= 10 ** (-0.2 / 20), peak


def test_ref_loudness_cache_and_failures(svc, monkeypatch, tmp_path):
    proc._ref_cache.clear()
    calls = []
    real = proc.mean_volume
    monkeypatch.setattr(proc, "mean_volume", lambda *a: calls.append(a) or real(*a))
    ref = svc.line(CID, GID, LID).ref_path
    a, b = proc.ref_loudness(ref), proc.ref_loudness(ref)
    assert a == b and a is not None and len(calls) == 1                   # кеш за (шлях, mtime)
    ref.touch()
    import os
    os.utime(ref, ns=(ref.stat().st_atime_ns, ref.stat().st_mtime_ns + 10**9))
    proc.ref_loudness(ref)
    assert len(calls) == 2                                                # mtime змінився → перевимір
    nope = tmp_path / "nope.wav"
    assert proc.ref_loudness(nope) is None and real(nope, []) is None
    assert proc.volume_stage(nope, [], ref) == []                         # не виміряно → без гучності


# ---------------------------------------------------------------- шумоговорення
def test_denoise_lowers_noise_floor(svc):
    f = _add(svc, _tone(2.0, amp=0.3, noise=0.006))                      # тон 0.25–1.75 с на шумі ≈ −44 дБ
    svc.set_settings({"auto_trim": False, "loudness": False})
    svc.approve(CID, GID, LID, f)
    raw = _read(GAME)
    svc.set_settings({"denoise": True})
    svc.approve(CID, GID, LID, f)
    den = _read(GAME)
    quiet = lambda s: s[int(0.03 * 22050):int(0.2 * 22050)] + s[int(1.8 * 22050):int(1.97 * 22050)]  # noqa: E731
    assert _rms_db(quiet(raw)) - _rms_db(quiet(den)) >= 6
    tone = lambda s: s[int(0.6 * 22050):int(1.4 * 22050)]  # noqa: E731
    assert abs(_rms_db(tone(raw)) - _rms_db(tone(den))) < 1.5            # голос не псується


# ---------------------------------------------------------------- «Як у грі»
def test_preview_equals_game_export_and_caches(svc, monkeypatch):
    f = _add(svc, _tone(1.5))
    svc.set_trim(CID, GID, LID, f, 0.1, 1.4)
    svc.set_tempo(CID, GID, LID, f, 1.2)
    svc.set_settings({"denoise": True})
    p = svc.preview(CID, GID, LID, f)
    assert p.parent == core.PREVIEW_DIR and not GAME.exists()             # незатверджений — копії для гри немає
    svc.approve(CID, GID, LID, f)
    assert p.read_bytes() == GAME.read_bytes()                            # байт у байт той самий ланцюжок
    n = []
    real = core.export_take
    monkeypatch.setattr(core, "export_take", lambda *a: n.append(1) or real(*a))
    assert svc.preview(CID, GID, LID, f) == p and not n                   # кеш
    svc.set_tempo(CID, GID, LID, f, 1.1)
    p2 = svc.preview(CID, GID, LID, f)
    assert p2 != p and n                                                  # інший ланцюжок → інший файл
    svc.set_settings({"denoise": False})
    assert svc.preview(CID, GID, LID, f) not in (p, p2)
    with pytest.raises(StudioError):
        svc.preview(CID, GID, LID, "nope.take9.wav")
    svc.delete(CID, GID, LID, f)
    assert svc.preview(CID, GID, LID, f).exists()


def test_preview_cache_is_bounded(svc, monkeypatch):
    monkeypatch.setattr(proc, "PREVIEW_MAX", 3)
    f = _add(svc, _tone(1.0))
    made = []
    for i in range(5):
        svc.set_tempo(CID, GID, LID, f, 1.0 + 0.05 * (i + 1))
        made.append(svc.preview(CID, GID, LID, f))
        import os
        os.utime(made[-1], (1000 + i, 1000 + i))                          # детермінований «вік»
    left = sorted(core.PREVIEW_DIR.glob("*.wav"))
    assert len(left) == 3 and set(left) == set(made[2:])


# ---------------------------------------------------------------- API
def test_api_settings_tempo_preview(api):  # noqa: F811
    code, s = api("/api/settings")
    assert code == 200 and s == {"auto_trim": True, "denoise": False, "loudness": True}
    code, s = api("/api/settings", {"denoise": True})
    assert code == 200 and s["denoise"] is True and api("/api/settings")[1]["denoise"] is True
    assert api("/api/settings", {"bogus": True})[0] == 400
    assert api("/api/settings", {"denoise": "так"})[0] == 400
    api(f"/api/take?cid={CID}&gid={GID}&lid={LID}", raw=wav_bytes())
    body = {"cid": CID, "gid": GID, "lid": LID, "file": "peonyes1.take1.wav"}
    code, ln = api("/api/tempo", {**body, "tempo": 1.2})
    assert code == 200 and ln["takes"][0]["tempo"] == 1.2
    assert api("/api/tempo", {**body, "tempo": 2})[0] == 400
    assert api("/api/tempo", {**body, "tempo": "x"})[0] == 400
    assert api("/api/tempo", {"cid": CID})[0] == 400
    code, wav = api(f"/api/preview?cid={CID}&gid={GID}&lid={LID}&file=peonyes1.take1.wav")
    assert code == 200 and wav[:4] == b"RIFF"
    assert api(f"/api/preview?cid={CID}&gid={GID}&lid={LID}")[0] == 400
    assert api(f"/api/preview?cid={CID}&gid={GID}&lid={LID}&file=..%2Fx.wav")[0] == 404
    code, ln = api("/api/approve", {**body, "trim": False})               # застарілий параметр приймається
    assert code == 200 and ln["approved"]
