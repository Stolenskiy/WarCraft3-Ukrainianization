"""«Залишити оригінал»: необроблена копія оригіналу в game-files, .originals.json, взаємовиключність із дублем."""
import hashlib
import json
import wave

import pytest
from conftest import TMP_ROOT
from studio.catalog import looks_nonverbal
from studio.core import StudioError
from test_studio_core import api  # noqa: F401  (фікстура HTTP-клієнта)

CID, GID, LID = "units-orc", "peon", "peonyes1.wav"
GAME = TMP_ROOT / "game-files/Units/orc/peon/peonyes1.wav"
REL = "Units/orc/peon/peonyes1.wav"
MARK = TMP_ROOT / "game-files/.originals.json"
REF = {"ru": TMP_ROOT / "reference/units/orc/peon/peonyes1.wav", "en": TMP_ROOT / "reference-en/units/orc/peon/peonyes1.wav"}


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def take(svc):
    from test_studio_core import wav_bytes
    return svc.add_take(CID, GID, LID, wav_bytes())["takes"][-1]["file"]


def test_heuristic():
    for t in ("Угу!", "Хм.", "Ха-ха-ха!", "Ага", "Ох, ах", "ха-ха"):
        assert looks_nonverbal(False, t), t
    for t in ("Зроблю.", "Чого хочеш?", "", "Ну що, пішли?", None):
        assert not looks_nonverbal(False, t), t
    assert looks_nonverbal(True, "Зроблю.")


@pytest.mark.parametrize("lang", ["ru", "en"])
def test_keep_original_copies_bytes_and_marks(svc, lang):
    ln = svc.keep_original(CID, GID, LID, lang)
    assert ln["original"]["lang"] == lang and GAME.read_bytes() == REF[lang].read_bytes()
    assert json.loads(MARK.read_text()) == {REL: {"lang": lang, "sha256": sha(REF[lang])}}
    assert svc.progress(CID, GID)[0] == 1 and svc.catalogs_json()[0]["groups"][0]["done"] == 1


def test_exclusive_with_take_both_ways(svc):
    f = take(svc)
    svc.approve(CID, GID, LID, f)
    ln = svc.keep_original(CID, GID, LID, "en")
    assert ln["approved"] is None and ln["original"] and GAME.read_bytes() == REF["en"].read_bytes()
    assert svc.progress(CID, GID)[0] == 1
    ln = svc.approve(CID, GID, LID, f)                      # дубль замінює оригінал
    assert ln["original"] is None and ln["approved"] == f
    assert GAME.read_bytes() != REF["en"].read_bytes() and json.loads(MARK.read_text()) == {}


def test_clear_removes_file_and_entry(svc):
    svc.keep_original(CID, GID, LID, "ru")
    ln = svc.clear_original(CID, GID, LID)
    assert ln["original"] is None and not GAME.exists() and json.loads(MARK.read_text()) == {}
    assert svc.progress(CID, GID)[0] == 0
    svc.clear_original(CID, GID, LID)                       # повторно — без помилки


def test_state_persists(svc):
    from studio import core
    svc.keep_original(CID, GID, LID, "en")
    assert core.Service().line_json(CID, GID, svc.line(CID, GID, LID))["original"]["lang"] == "en"


def test_non_game_format_is_converted(svc):
    src = REF["en"]
    keep = src.read_bytes()
    try:
        import subprocess
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(src), "-ar", "44100", "-ac", "2", str(src.with_suffix(".t.wav"))], check=True)
        src.with_suffix(".t.wav").replace(src)
        svc.keep_original(CID, GID, LID, "en")
        with wave.open(str(GAME)) as w:
            assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (22050, 1, 2)
    finally:
        src.write_bytes(keep)


def test_errors(svc):
    with pytest.raises(StudioError):
        svc.keep_original(CID, GID, LID, "de")
    with pytest.raises(StudioError, match="англійського"):
        svc.keep_original("units-orc", "grunt", "gruntyes1.wav", "en")     # EN-пари немає
    assert not (TMP_ROOT / "game-files/Units/orc/grunt/gruntyes1.wav").exists()
    with pytest.raises(StudioError):
        svc.keep_original(CID, GID, "nope.wav", "ru")


def test_line_json_hint(svc):
    assert svc.group_json(CID, GID)["lines"][0]["orig_hint"] is False                  # «Зроблю.»
    what1 = next(x for x in svc.group_json(CID, GID)["lines"] if x["id"] == "peonwhat1.wav")
    assert what1["orig_hint"] is True                                                  # «Угу!»
    assert next(x for x in svc.group_json(CID, GID)["lines"] if x["id"] == "peondeath.wav")["orig_hint"]


def test_api(api):  # noqa: F811
    body = {"cid": CID, "gid": GID, "lid": LID}
    code, ln = api("/api/original", {**body, "lang": "en"})
    assert code == 200 and ln["original"]["lang"] == "en" and GAME.exists()
    assert api("/api/original", {**body, "lang": "xx"})[0] == 400
    assert api("/api/original", {"cid": CID, "gid": "grunt", "lid": "gruntyes1.wav", "lang": "en"})[0] == 400
    assert api("/api/original", {**body})[0] == 400
    code, ln = api("/api/original/clear", body)
    assert code == 200 and ln["original"] is None and not GAME.exists()


def test_install_plan_includes_original(svc, tmp_path):
    import install_voices as iv
    svc.keep_original(CID, GID, LID, "ru")
    game = tmp_path / "game"
    game.mkdir()
    p = iv.plan(game, TMP_ROOT)
    assert [f["rel"] for f in p["files"]] == [REL]               # .originals.json у план не потрапляє
    iv.apply(game, TMP_ROOT)
    assert (game / REL).read_bytes() == REF["ru"].read_bytes()


def test_corrupt_marks_file_is_rebuilt_and_garbage_ref_fails(svc):
    MARK.parent.mkdir(parents=True, exist_ok=True)
    MARK.write_text("{не json")
    svc.keep_original(CID, GID, LID, "ru")
    assert list(json.loads(MARK.read_text())) == [REL]
    MARK.write_text("{не json")
    svc.clear_original(CID, GID, LID)                        # запису немає в зіпсованому файлі — не падаємо
    assert not GAME.exists()
    keep = REF["en"].read_bytes()
    try:
        REF["en"].write_bytes(b"not audio at all")
        with pytest.raises(StudioError, match="перетворити"):
            svc.keep_original(CID, GID, LID, "en")
        assert not GAME.exists()
    finally:
        REF["en"].write_bytes(keep)


def test_clean_ru_whisper_garbage():
    """Галюцинації Whisper: вирізати хвіст зі справжніх реплік, сміття з латиницею → «ненадійне», вигуки → no_speech."""
    from studio.catalog import NO_SPEECH, UNRELIABLE, clean_ru
    assert clean_ru("«Т si наrawы слоя вир brain не будет уравнение?»") == (UNRELIABLE, "unreliable")
    assert clean_ru("Нway!") == (UNRELIABLE, "unreliable")
    assert clean_ru("Продолжение следует...") == (NO_SPEECH, "no_speech")
    assert clean_ru("Субтитры создавал DimaTorzok") == (NO_SPEECH, "no_speech")
    assert clean_ru("Редактор субтитров А.Семкин Корректор А.Егорова") == (NO_SPEECH, "no_speech")
    assert clean_ru("ВООДУШЕВЛЯЮЩАЯ МУЗЫКА") == (NO_SPEECH, "no_speech")
    assert clean_ru("Оооооооооооо") == (NO_SPEECH, "no_speech")
    assert clean_ru("Режет даже тяжелый доспех. Продолжение следует...") == ("Режет даже тяжелый доспех.", None)
    assert clean_ru("Такой уж я. Субтитры создавал DimaTorzok") == ("Такой уж я.", None)
    assert clean_ru("«Реальность — штука жестокая!»") == ("Реальность — штука жестокая!", None)
    assert clean_ru("Ха-ха-ха-ха-ха-ха-ха-ха") == ("Ха-ха-ха…", None)
    assert clean_ru("Зроблю.") == ("Зроблю.", None)
