"""Еквалайзер персонажа: пресети, ffmpeg-фільтри, профілі, призначення, повторний експорт, API."""
import json
import subprocess

import pytest
from conftest import REPO, TMP_ROOT, synth
from studio import eq
from studio.core import StudioError
from test_studio_core import CID, GID, LID, api, wav_bytes  # noqa: F401  (api — фікстура)

ORC_UNITS = ["battroll", "cairne", "grunt", "headhunter", "hellscream", "heroblademaster", "herofarseer",
             "heroshadowhunter", "herotaurenchieftain", "kotobeast", "peon", "shaman", "spiritwalker", "tauren",
             "thrall", "witchdoctor", "wolfrider", "wyvernrider"]
PROFILE = {"name": "Мій", "enabled": True, "gain_db": -1, "bands": [
    {"type": "highpass", "freq_hz": 80, "gain_db": 0, "q": 0.71},
    {"type": "lowshelf", "freq_hz": 150, "gain_db": 3, "q": 0.71},
    {"type": "peaking", "freq_hz": 2500, "gain_db": -2, "q": 1.2},
    {"type": "highshelf", "freq_hz": 8000, "gain_db": 2, "q": 0.71},
    {"type": "lowpass", "freq_hz": 12000, "gain_db": 0, "q": 0.71}]}


def ffmpeg_ok(filters):
    src = synth(TMP_ROOT / "eq-in.wav", 0.5)
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(src), "-af", ",".join(filters),
                        str(TMP_ROOT / "eq-out.wav")], capture_output=True)
    return r.returncode == 0, r.stderr


def test_presets_valid_and_cover_orcs():
    presets = eq.load_presets()
    assert {"neutral", "orc-base"} <= set(presets)
    assert {f"orc-{u}" for u in ORC_UNITS} <= set(presets)
    for pid, p in presets.items():
        hp = [b for b in p["bands"] if b["type"] == "highpass"]
        assert hp and 70 <= hp[0]["freq_hz"] <= 90, pid
        assert all(abs(b["gain_db"]) <= 6 for b in p["bands"]) and abs(p["gain_db"]) <= 6, pid
        assert ffmpeg_ok(eq.to_ffmpeg(p))[0], pid


def test_presets_match_real_orc_folders():
    real = REPO.parent / "wc3-ua-voice/reference/units/orc"      # лише в локальному середовищі автора
    if real.is_dir():
        assert {d.name for d in real.iterdir() if d.is_dir()} <= {k.removeprefix("orc-") for k in eq.load_presets()}


def test_to_ffmpeg():
    fl = eq.to_ffmpeg(eq.validate(PROFILE))
    assert fl == ["highpass=f=80:t=q:w=0.71", "bass=g=3:f=150:t=q:w=0.71", "equalizer=f=2500:t=q:w=1.2:g=-2",
                  "treble=g=2:f=8000:t=q:w=0.71", "lowpass=f=12000:t=q:w=0.71", "volume=-1dB"]
    assert ffmpeg_ok(fl)[0]
    assert eq.to_ffmpeg({**PROFILE, "enabled": False}) == []
    assert eq.to_ffmpeg({"name": "x", "bands": [{"type": "peaking", "freq_hz": 1000, "gain_db": 0, "q": 1}]}) == []


def test_amount_scales_band_gains():
    base = {"name": "x", "bands": [{"type": "highpass", "freq_hz": 80, "gain_db": 0, "q": 0.71},
                                   {"type": "peaking", "freq_hz": 1000, "gain_db": 4, "q": 1.0},
                                   {"type": "highshelf", "freq_hz": 6000, "gain_db": -2, "q": 0.71}]}
    assert eq.validate(base)["amount"] == 1                                   # типово 100 %
    full = eq.to_ffmpeg(eq.validate(base))
    assert eq.to_ffmpeg(eq.validate({**base, "amount": 1.5}))[1:] == ["equalizer=f=1000:t=q:w=1:g=6", "treble=g=-3:f=6000:t=q:w=0.71"]
    assert eq.to_ffmpeg(eq.validate({**base, "amount": 0.5}))[1:] == ["equalizer=f=1000:t=q:w=1:g=2", "treble=g=-1:f=6000:t=q:w=0.71"]
    assert eq.to_ffmpeg(eq.validate({**base, "amount": 1}))[1:] == full[1:] and full[0].startswith("highpass")   # зріз низів не множиться
    assert eq.to_ffmpeg(eq.validate({**base, "amount": 0})) == []              # 0 % = вимкнено
    big = {"name": "x", "amount": 2, "bands": [{"type": "peaking", "freq_hz": 1000, "gain_db": 9, "q": 1}]}
    assert eq.to_ffmpeg(eq.validate(big)) == ["equalizer=f=1000:t=q:w=1:g=12"]  # стеля ±12 дБ
    for bad in (-0.1, 2.5, "1", None):
        with pytest.raises(eq.EqError):
            eq.validate({**base, "amount": bad})
    assert ffmpeg_ok(eq.to_ffmpeg(eq.validate({**base, "amount": 1.5})))[0]


@pytest.mark.parametrize("bad", [
    None, {"name": ""}, {"name": "x", "bands": "no"}, {"name": "x", "bands": [{"type": "bell", "freq_hz": 100}]},
    {"name": "x", "bands": [{"type": "peaking", "freq_hz": 5}]},
    {"name": "x", "bands": [{"type": "peaking", "freq_hz": 100, "gain_db": 40}]},
    {"name": "x", "bands": [{"type": "peaking", "freq_hz": 100, "q": 0}]},
    {"name": "x", "bands": [{"type": "peaking", "freq_hz": "100"}]},
    {"name": "x", "gain_db": 99}, {"name": "x", "bands": [{"type": "peaking", "freq_hz": 100}] * 9}])
def test_validation_rejects(bad):
    with pytest.raises(eq.EqError):
        eq.validate(bad)


def test_defaults_and_crud(svc):
    assert svc.eq_json(CID, "peon")["selected"] == "orc-peon"
    assert eq.default_id("units-orc", "unknown", svc.eq.presets) == "orc-base"
    assert eq.default_id("units-human", "footman", svc.eq.presets) == "neutral"
    r = svc.eq_save(CID, GID, PROFILE)
    pid = r["saved_id"]
    assert r["selected"] == pid and any(p["id"] == pid and not p["builtin"] for p in r["profiles"])
    r = svc.eq_save(CID, GID, {**PROFILE, "name": "Новіше"}, pid)
    assert next(p for p in r["profiles"] if p["id"] == pid)["name"] == "Новіше"
    with pytest.raises(StudioError, match="лише для читання"):
        svc.eq_save(CID, GID, PROFILE, "orc-peon")
    with pytest.raises(StudioError):
        svc.eq_save(CID, GID, PROFILE, "u-nope")
    with pytest.raises(StudioError):
        svc.eq_save(CID, GID, {"name": ""})
    with pytest.raises(StudioError):
        svc.eq_delete(CID, GID, "orc-peon")
    with pytest.raises(StudioError):
        svc.eq_delete(CID, GID, "u-nope")
    assert svc.eq_delete(CID, GID, pid)["selected"] == "orc-peon"      # призначення зникло з профілем


def test_assignment_persists(svc):
    from studio import core
    pid = svc.eq_save(CID, "grunt", PROFILE)["saved_id"]
    svc.eq_assign(CID, GID, "orc-tauren")
    s2 = core.Service()                                                # новий процес читає eq.json
    assert s2.eq_json(CID, "grunt")["selected"] == pid and s2.eq_json(CID, GID)["selected"] == "orc-tauren"
    assert s2.eq_assign(CID, GID, None)["selected"] == "orc-peon"
    with pytest.raises(StudioError):
        s2.eq_assign(CID, GID, "u-nope")
    (TMP_ROOT / "data/studio/eq.json").write_text("[broken")           # зіпсований файл → типові
    assert core.Service().eq_json(CID, GID)["selected"] == "orc-peon"


def test_export_uses_group_eq(svc):
    take = {"file": "x"}
    assert svc._export_filters(CID, GID, take, False) == eq.to_ffmpeg(svc.eq.presets["orc-peon"])
    assert svc._export_filters(CID, GID, take, True)[0].startswith("silenceremove")
    assert svc._export_filters("units-human", "footman", take, False) == ["highpass=f=70:t=q:w=0.71"]


def test_reexport_group(svc):
    svc.add_take(CID, GID, LID, wav_bytes())
    svc.approve(CID, GID, LID, "peonyes1.take1.wav")
    r = svc.reexport_group(CID, GID)
    assert r["done"] == [LID] and r["failed"] == []
    assert "EQ «" in r["lines"][0]["history"][-1]["action"]
    (TMP_ROOT / "audio/self-recorded" / CID / GID / "peonyes1.take1.wav").unlink()
    assert svc.reexport_group(CID, GID)["failed"] == [LID]
    assert svc.reexport_group(CID, "grunt")["done"] == []


def test_stale_game_files(svc):
    svc.add_take(CID, GID, LID, wav_bytes())
    line = svc.approve(CID, GID, LID, "peonyes1.take1.wav")
    assert line["stale"] is False and svc.eq_json(CID, GID)["stale"] == 0
    svc.eq_assign(CID, GID, "orc-tauren")                                   # змінили EQ → файл у грі застарів
    assert svc.eq_json(CID, GID)["stale"] == 1
    assert svc.group_json(CID, GID)["lines"][0]["stale"] is True
    r = svc.reexport_group(CID, GID)
    assert r["lines"][0]["stale"] is False and svc.eq_json(CID, GID)["stale"] == 0
    svc.set_settings({"denoise": True})                                     # змінили обробку → знову застарів
    assert svc.eq_json(CID, GID)["stale"] == 1


def test_eq_api(api):  # noqa: F811
    code, d = api(f"/api/eq?cid={CID}&gid={GID}")
    assert code == 200 and d["selected"] == "orc-peon" and len(d["profiles"]) >= 20
    code, d = api("/api/eq/profile", {"cid": CID, "gid": GID, "profile": PROFILE})
    pid = d["saved_id"]
    assert code == 200 and d["selected"] == pid
    code, d = api("/api/eq/profile", {"cid": CID, "gid": GID, "profile": PROFILE, "id": "orc-peon"})
    assert code == 400 and "лише для читання" in d["error"]
    code, d = api("/api/eq/profile", {"cid": CID, "gid": GID, "profile": {"name": ""}})
    assert code == 400
    code, d = api("/api/eq/assign", {"cid": CID, "gid": GID, "profile_id": "orc-tauren"})
    assert code == 200 and d["selected"] == "orc-tauren"
    assert api("/api/eq/assign", {"cid": CID, "gid": GID, "profile_id": "nope"})[0] == 400
    assert api("/api/eq/assign", {"cid": CID})[0] == 400
    assert api("/api/eq/delete", {"cid": CID, "gid": GID, "id": pid})[0] == 200
    assert api("/api/eq/delete", {"cid": CID, "gid": GID, "id": pid})[0] == 400
    code, r = api("/api/eq/reexport", {"cid": CID, "gid": GID})
    assert code == 200 and r["done"] == []
    assert api("/api/eq?cid=nope&gid=x")[0] == 404
    assert api("/api/eq")[0] == 400
    assert json.loads((TMP_ROOT / "data/studio/eq.json").read_text())["profiles"] == {}


def test_shelf_q_is_fixed():
    """У полиць Q не керується (Web Audio його ігнорує): validate і ffmpeg однаково дають 0.71."""
    p = {"name": "П", "bands": [{"type": "lowshelf", "freq_hz": 150, "gain_db": 3, "q": 5},
                                {"type": "highshelf", "freq_hz": 8000, "gain_db": 2},
                                {"type": "peaking", "freq_hz": 1000, "gain_db": 2, "q": 5}]}
    clean = eq.validate(p)
    assert [b["q"] for b in clean["bands"]] == [0.71, 0.71, 5.0]
    # навіть непровалідований профіль не передає в ffmpeg довільний Q полиці
    fl = eq.to_ffmpeg({"bands": [{"type": "lowshelf", "freq_hz": 150, "gain_db": 3, "q": 5}]})
    assert fl == ["bass=g=3:f=150:t=q:w=0.71"]
