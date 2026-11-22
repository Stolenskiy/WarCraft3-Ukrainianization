"""Пресет персонажа: перевірка, ffmpeg-фільтри (висота, форманти, гроул, простір) на синтетиці, пропозиції з voice bible,
стан у data/studio/<cid>.json, ланцюжок експорту й «застарілі» файли гри, ШІ-дублі, API."""
import json
import math
import struct
import subprocess
import wave
from pathlib import Path

import pytest
from conftest import REPO, TMP_ROOT, synth
from studio import character as ch
from studio import core
from studio.core import StudioError
from test_studio_core import CID, GID, LID, _read_game, _zcr_hz, api, wav_bytes  # noqa: F401

ON = {"enabled": True, "pitch_st": 0.0, "formant_pct": 0.0, "drive": 0.0, "reverb": 0.0, "tail_s": 0.4}
STATE = TMP_ROOT / "data/studio/units-orc.json"


def _render(src: Path, filters: list[str], name: str) -> list[int]:
    out = TMP_ROOT / name
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(src), "-af", ",".join(filters) or "anull",
                    "-ar", "22050", "-ac", "1", "-sample_fmt", "s16", str(out)], check=True)
    with wave.open(str(out)) as w:
        return list(struct.unpack(f"<{w.getnframes()}h", w.readframes(w.getnframes())))


def _band_db(s: list[int], lo: float, hi: float, step: float = 50) -> float:
    """Енергія смуги (Goertzel по сітці частот), дБ — stdlib, без numpy."""
    tot, f = 0.0, lo
    while f <= hi:
        k = 2 * math.cos(2 * math.pi * f / 22050)
        a = b = 0.0
        for x in s:
            a, b = x + k * a - b, a
        tot += a * a + b * b - k * a * b
        f += step
    return 10 * math.log10(tot + 1e-9)


def _buzz(path: Path) -> Path:
    """Гармонійний «голос»: імпульси 120 Гц через резонанс 1 кГц (форманта)."""
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    "aevalsrc='if(lt(mod(t*120,1),0.02),0.8,0)':s=22050:d=0.8", "-af",
                    "lowpass=f=3000,equalizer=f=1000:t=q:w=3:g=24,volume=-24dB", "-ac", "1", "-sample_fmt", "s16",
                    str(path)], check=True)
    return path


# ---------------------------------------------------------------- перевірка й фільтри
def test_validate_defaults_rounding_and_errors():
    assert ch.validate({}) == ch.DEFAULT
    assert ch.validate({"pitch_st": -1.234, "enabled": 1})["pitch_st"] == -1.23
    for bad in (None, [], {"pitch_st": 7}, {"drive": "x"}, {"reverb": True}, {"tail_s": 0}, {"formant_pct": float("nan")}):
        with pytest.raises(ch.CharacterError):
            ch.validate(bad)


def test_to_ffmpeg_parts():
    assert ch.to_ffmpeg({**ON, "enabled": False, "pitch_st": 3}) == ([], [])
    assert ch.to_ffmpeg(ON) == ([], [])
    v, fx = ch.to_ffmpeg({**ON, "pitch_st": 2})
    assert v[1] == "asetrate=24750" and v[3].startswith("atempo=") and v[4].startswith("afftfilt=") and fx == []
    v, _ = ch.to_ffmpeg({**ON, "formant_pct": -10})
    assert len(v) == 1 and "floor(b/0.9000)" in v[0]
    _, fx = ch.to_ffmpeg({**ON, "drive": 50, "reverb": 40, "tail_s": 1.0})
    assert "asoftclip=type=tanh" in fx and fx[3] == "tremolo=f=30:d=0.20" and fx[-1].startswith("aecho=0.9:0.9:110|190|290|410:")


def test_pitch_moves_tone_keeps_duration(clean_root):
    src = synth(TMP_ROOT / "tone.wav", 0.8, 300)
    out = _render(src, ch.to_ffmpeg({**ON, "pitch_st": 4})[0], "p.wav")
    assert abs(len(out) / 22050 - 0.8) < 0.03
    assert abs(_zcr_hz(out[2000:-2000]) - 300 * 2 ** (4 / 12)) < 12


def test_formants_move_envelope_not_pitch(clean_root):
    src = _buzz(TMP_ROOT / "buzz.wav")
    raw = _render(src, [], "raw.wav")
    for pct, louder in ((-15, (650, 900)), (15, (1100, 1400))):
        out = _render(src, ch.to_ffmpeg({**ON, "formant_pct": pct})[0], f"f{pct}.wav")
        assert len(out) == len(raw)
        lo, hi = louder
        gain = _band_db(out, lo, hi) - _band_db(raw, lo, hi)
        ref = _band_db(out, 950, 1050) - _band_db(raw, 950, 1050)
        assert gain - ref > 3, f"форманта мала зсунутися в {lo}–{hi} Гц (Δ {gain - ref:.1f} дБ)"
        assert _band_db(out, 110, 130, 5) > _band_db(out, 135, 160, 5) + 6   # основний тон лишився 120 Гц


def test_effects_render_and_reverb_adds_tail(clean_root):
    src = synth(TMP_ROOT / "tone.wav", 0.8)
    v, fx = ch.to_ffmpeg({**ON, "pitch_st": -3, "formant_pct": -10, "drive": 60, "reverb": 50, "tail_s": 1.0})
    out = _render(src, v + fx, "all.wav")
    assert len(out) / 22050 > 1.1 and max(abs(x) for x in out[-6000:]) > 30   # хвіст простору після кінця голосу


# ---------------------------------------------------------------- пропозиції з voice bible
def _sug(race, unit):
    info = ch.bible_processing(REPO / f"docs/voice-bible/{race}.md")[unit]
    return ch.suggest(race, info["proc"], info["timbre"])


def test_real_bibles_give_distinct_presets():
    for race in ("orc", "human", "undead", "nightelf"):
        units = ch.bible_processing(REPO / f"docs/voice-bible/{race}.md")
        assert len(units) >= 10 and sum(bool(u["proc"]) for u in units.values()) >= 10
    grunt, why = _sug("orc", "grunt")
    assert grunt["enabled"] is False and grunt["pitch_st"] == -1.9 and grunt["formant_pct"] == -10 and grunt["reverb"] == 0
    assert grunt["drive"] > 30 and any("pitch ×0.95" in w for w in why)
    assert _sug("orc", "peon")[0]["pitch_st"] > grunt["pitch_st"]                 # орчатник «менший» за ґрунта
    assert _sug("human", "rifleman")[0]["pitch_st"] == 1.7
    banshee, acolyte = _sug("undead", "banshee")[0], _sug("undead", "acolyte")[0]
    assert banshee["reverb"] > acolyte["reverb"] > 0 and banshee["tail_s"] > 1.2
    assert _sug("nightelf", "herowarden")[0]["reverb"] == 0 and _sug("human", "bloodelfdragonhawk")[0]["formant_pct"] == 5
    assert _sug("orc", "shaman")[0]["tail_s"] == 0.2


def test_suggest_edge_cases(tmp_path):
    assert ch.suggest(None) == (ch.DEFAULT, [])
    p, why = ch.suggest("orc", "race chain + formant +5% і pitch 1,10")
    assert p["formant_pct"] == 5 and p["pitch_st"] == 0.7 and len(why) == 2
    assert ch.bible_processing(tmp_path / "none.md") == {}
    md = tmp_path / "x.md"
    md.write_text("### a — А\n**Обробка:** перший\nрядок\n\n## Інше\n**Обробка:** чуже\n", encoding="utf-8")
    assert ch.bible_processing(md) == {"a": {"proc": "перший рядок", "timbre": ""}}
    assert ch.bible_processing(md) is ch.bible_processing(md)                   # кеш за mtime


# ---------------------------------------------------------------- стан, експорт, A/B
def test_default_is_bible_suggestion_and_off(svc):
    j = svc.character_json(CID, GID)
    assert j["custom"] is False and j["preset"]["enabled"] is False and j["preset"] == j["suggestion"]
    assert j["why"][0].startswith("раса:") and j["limits"]["pitch_st"] == [-6.0, 6.0] and j["stale"] == 0
    assert svc.character_filters(CID, GID) == ([], [])
    assert svc.character_json("units-human", "footman")["preset"]["reverb"] == 10       # аркуша немає → палітра раси
    with pytest.raises(StudioError):
        svc.character_json(CID, "nope")


def test_set_persists_orders_chain_and_marks_stale(svc):
    f = svc.add_take(CID, GID, LID, wav_bytes())["takes"][-1]["file"]
    svc.approve(CID, GID, LID, f)
    before = _read_game()[1]
    j = svc.character_set(CID, GID, {**ON, "pitch_st": 4, "reverb": 30})
    assert j["custom"] is True and j["stale"] == 1                                # файл гри зроблено без пресета
    assert json.loads(STATE.read_text())["characters"][GID]["pitch_st"] == 4
    chain = svc._export_filters(CID, GID, {"file": f}, False, svc.line(CID, GID, LID))
    at = lambda pre: next(i for i, x in enumerate(chain) if x.startswith(pre))   # noqa: E731
    assert at("asetrate=27781") < at("afftfilt") < at("highpass") < at("aecho") < at("volume=") < at("alimiter")
    assert svc.reexport_group(CID, GID)["done"] == [LID] and svc.character_json(CID, GID)["stale"] == 0
    after = _read_game()[1]
    assert after != before and abs(_zcr_hz(after[3000:9000]) - 440 * 2 ** (4 / 12)) < 25
    assert core.Service().character(CID, GID)["pitch_st"] == 4                    # новий сервіс читає зі стану
    j = svc.character_set(CID, GID, None)
    assert j["custom"] is False and "characters" in json.loads(STATE.read_text()) and j["stale"] == 1
    assert svc.character_set(CID, GID, None)["custom"] is False                   # повторне скидання — без запису
    with pytest.raises(StudioError):
        svc.character_set(CID, GID, {"pitch_st": 99})


def test_old_or_broken_state_falls_back(svc):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({"version": 3, "groups": {}}))                    # старий файл без "characters"
    assert core.Service().character_json(CID, GID)["custom"] is False
    STATE.write_text(json.dumps({"version": 3, "groups": {}, "characters": {GID: {"pitch_st": "x"}}}))
    s2 = core.Service()
    assert s2.character_json(CID, GID)["custom"] is False and s2.character_filters(CID, GID) == ([], [])
    STATE.write_text(json.dumps({"version": 3, "groups": {}, "characters": []}))
    assert core.Service().character_set(CID, GID, ON)["custom"] is True


def test_ai_take_gets_character_too(svc):
    """ШІ-дубль (source "ai") іде тим самим ланцюжком: пресет персонажа діє і на нього."""
    f = svc.add_take(CID, GID, LID, wav_bytes())["takes"][-1]["file"]
    t = next(x for x in svc.store(CID).entry(GID, LID)["takes"] if x["file"] == f)
    t.update(source="ai", engine="fake")
    svc.character_set(CID, GID, {**ON, "pitch_st": -5})
    svc.approve(CID, GID, LID, f)
    assert abs(_zcr_hz(_read_game()[1][3000:9000]) - 440 * 2 ** (-5 / 12)) < 25


def test_character_audio_renders_and_caches(svc, monkeypatch):
    f = svc.add_take(CID, GID, LID, wav_bytes())["takes"][-1]["file"]
    p = svc.character_audio(CID, GID, LID, f)                                     # вимкнена пропозиція теж звучить
    assert p.name.startswith("char-") and p.exists()
    calls = []
    monkeypatch.setattr("studio.svc.character_svc.export_take", lambda *a: calls.append(a) or False)
    assert svc.character_audio(CID, GID, LID, f) == p and not calls               # з кешу
    svc.character_set(CID, GID, {**ON, "drive": 30})
    with pytest.raises(StudioError, match="персонажа"):
        svc.character_audio(CID, GID, LID, f)
    (TMP_ROOT / "audio/self-recorded" / CID / GID / f).unlink()
    with pytest.raises(StudioError, match="не знайдено"):
        svc.character_audio(CID, GID, LID, f)


def test_character_api(api):  # noqa: F811
    code, j = api(f"/api/character?cid={CID}&gid={GID}")
    assert code == 200 and j["custom"] is False
    code, j = api("/api/character", {"cid": CID, "gid": GID, "preset": {**ON, "formant_pct": -8}})
    assert code == 200 and j["custom"] is True and j["preset"]["formant_pct"] == -8
    assert api("/api/character", {"cid": CID, "gid": GID, "preset": {"drive": 500}})[0] == 400
    assert api("/api/character", {"cid": CID})[0] == 400
    assert api(f"/api/character?cid={CID}&gid=nope")[0] == 404
    code, _ = api(f"/api/take?cid={CID}&gid={GID}&lid={LID}", raw=wav_bytes())
    code, body = api(f"/api/character/audio?cid={CID}&gid={GID}&lid={LID}&file=peonyes1.take1.wav")
    assert code == 200 and body[:4] == b"RIFF"
    assert api(f"/api/character/audio?cid={CID}&gid={GID}&lid={LID}&file=nope.wav")[0] == 404
    assert api("/api/character", {"cid": CID, "gid": GID, "preset": None})[1]["custom"] is False
