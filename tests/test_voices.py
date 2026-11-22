"""Голоси спільноти: публікація, перевірка пакетів, вибір голосу, встановлення суміші авторів, API."""
import http.client
import json
import shutil
import wave

import check_voices
import install_voices as iv
import pytest
from conftest import TMP_ROOT, synth
from studio import server as _studio_server  # noqa: F401  (імпорт до зміни WC3UA_ROOT)

import voices

LINES = ["orc/peon/peonyes1", "orc/peon/peonwhat1", "orc/grunt/gruntyes1", "human/footman/footmanyes1"]


def pcm(p):
    with wave.open(str(p), "rb") as w:
        return w.readframes(w.getnframes())


def mkroot(tmp_path, name="repo"):
    root = tmp_path / name
    (root / "data").mkdir(parents=True)
    (root / "data/inventory-units.csv").write_text(
        "file,category\n" + "".join(f"{x}.wav,units\n" for x in LINES), encoding="utf-8")
    return root


def record(root, freq, lines=LINES):
    """Підміна game-files/ новим набором «затверджених» дублів (синус із частотою freq)."""
    shutil.rmtree(root / "game-files", ignore_errors=True)
    for x in lines:
        synth(root / f"game-files/Units/{x}.wav", freq=freq)


def pub(root, nick="alice", freq=440, lines=LINES):
    record(root, freq, lines)
    return voices.publish(nick, nick, root, consent=True)


# ---------------------------------------------------------------- publish
def test_publish_creates_valid_flac_and_manifest(tmp_path):
    root = mkroot(tmp_path)
    r = pub(root)
    assert (r["added"], r["updated"], r["removed"], r["files"]) == (4, 0, 0, 4) and r["total_mb"] > 0
    assert r["git"][0] == "git switch -c voices/alice" and any(c.startswith("git commit") for c in r["git"])
    f = root / "voices/alice/units/orc/peon/peonyes1.flac"
    i = voices.flac_info(f)
    assert (i["rate"], i["channels"], i["bits"], i["tags"]) == (22050, 1, 16, 0) and f.stat().st_size < 1_000_000
    man = json.loads((root / "voices/alice/manifest.json").read_text())
    ent = man["Units/orc/peon/peonyes1.wav"]
    assert ent["sha256"] == voices.sha256(f) and abs(ent["dur"] - 0.8) < 0.05 and ent["peak_db"] < 0
    vj = json.loads((root / "voices/alice/voice.json").read_text())
    assert vj["license"] == "CC BY 4.0" and vj["consent"] is True and vj["id"] == "alice" and "@" not in json.dumps(vj)
    assert check_voices.check(root) == []
    again = voices.publish("alice", "alice", root, consent=True)          # детермінізм: повторно — без змін
    assert (again["added"], again["updated"], again["unchanged"]) == (0, 0, 4)


def test_publish_syncs_updates_and_removals(tmp_path):
    root = mkroot(tmp_path)
    pub(root)
    (root / "game-files/Units/orc/grunt/gruntyes1.wav").unlink()          # дубль знято з вибору
    synth(root / "game-files/Units/orc/peon/peonyes1.wav", freq=300)      # перезаписано
    r = voices.publish("alice", "alice", root, consent=True)
    assert (r["added"], r["updated"], r["removed"], r["unchanged"]) == (0, 1, 1, 2)
    assert not (root / "voices/alice/units/orc/grunt").exists()          # порожня тека прибрана
    assert "Units/orc/grunt/gruntyes1.wav" not in json.loads((root / "voices/alice/manifest.json").read_text())
    assert check_voices.check(root) == []


def test_publish_refusals(tmp_path):
    root = mkroot(tmp_path)
    record(root, 440)
    with pytest.raises(voices.VoiceError, match="згода"):
        voices.publish("alice", "alice", root, consent=False)
    with pytest.raises(voices.VoiceError, match="@"):
        voices.publish("alice", "me@example.com", root, consent=True)
    for bad in ("a@b", "A", "x", "a/b", "../x"):
        with pytest.raises(voices.VoiceError):
            voices.publish(bad, "ok", root, consent=True)
    assert not (root / "voices").exists()
    shutil.rmtree(root / "game-files")
    with pytest.raises(voices.VoiceError, match="немає що публікувати"):
        voices.publish("alice", "alice", root, consent=True)


def test_publish_skips_non_unit_and_bad_duration(tmp_path):
    root = mkroot(tmp_path)
    record(root, 440, LINES[:1])
    synth(root / "game-files/Sounds/ui/click.wav")
    synth(root / "game-files/Units/orc/peon/peonshort1.wav", sec=0.1)
    r = voices.publish("alice", "alice", root, consent=True)
    assert r["files"] == 1 and {s["rel"] for s in r["skipped"]} == {"Sounds/ui/click.wav", "Units/orc/peon/peonshort1.wav"}


def test_cli_publish(tmp_path, monkeypatch, capsys):
    root = mkroot(tmp_path)
    record(root, 440)
    monkeypatch.setenv("WC3UA_ROOT", str(root))
    assert voices.main(["publish", "--author", "alice"]) == 1 and "CONSENT=1" in capsys.readouterr().out
    assert voices.main(["publish", "--author", "alice", "--consent"]) == 0
    assert "git push -u origin voices/alice" in capsys.readouterr().out
    monkeypatch.setattr(check_voices, "check", lambda r: [])
    assert check_voices.main([]) == 0


# ---------------------------------------------------------------- check_voices
def test_check_voices_catches_problems(tmp_path):
    root = mkroot(tmp_path)
    assert check_voices.check(root) == []                                 # voices/ немає — нічого перевіряти
    pub(root)
    a = root / "voices/alice"
    f = a / "units/orc/peon/peonyes1.flac"
    good = f.read_bytes()

    def errs(sub):
        return [e for e in check_voices.check(root) if sub in e]

    synth(root / "t.wav")                                                 # неправильна частота дискретизації
    import subprocess
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(root / "t.wav"), "-ar", "44100", "-map_metadata", "-1",
                    str(f)], check=True)
    assert errs("формат 44100") and errs("sha256 не збігається")
    f.write_bytes(good + b"x")                                            # sha
    assert errs("sha256 не збігається")
    f.write_bytes(good)
    assert check_voices.check(root) == []
    (a / "units/orc/peon/notes.txt").write_text("hi")                    # сторонні файли
    (a / "README.md").write_text("hi")
    assert errs("notes.txt: сторонній") and errs("README.md: сторонній")
    (a / "units/orc/peon/notes.txt").unlink()
    (a / "README.md").unlink()
    (root / "voices/stray.flac").write_bytes(b"x")
    assert errs("stray.flac: сторонній")
    (root / "voices/stray.flac").unlink()
    f.write_bytes(good + b"\0" * 1_000_001)                               # завеликий
    assert errs("байт >")
    f.write_bytes(good)
    shutil.copy(f, a / "units/orc/peon/peonghost9.flac")                 # невідома репліка і немає в маніфесті
    assert errs("невідома репліка") and errs("немає в manifest.json")
    (a / "units/orc/peon/peonghost9.flac").unlink()
    man = json.loads((a / "manifest.json").read_text())
    man["Units/orc/peon/peonyes2.wav"] = {"sha256": "0" * 64, "dur": 1, "peak_db": 0}
    (a / "manifest.json").write_text(json.dumps(man))
    assert errs("немає у units/")
    (a / "manifest.json").write_text("{")
    assert errs("некоректний JSON")


def test_check_voices_bad_voice_json(tmp_path):
    root = mkroot(tmp_path)
    pub(root)
    vj = root / "voices/alice/voice.json"
    base = json.loads(vj.read_text())
    for patch, sub in (({"license": "MIT"}, "license"), ({"consent": False}, "consent"), ({"id": "bob"}, "id має"),
                       ({"name": "me@x.com"}, "«@»"), ({"name": ""}, "name")):
        vj.write_text(json.dumps({**base, **patch}))
        assert any(sub in e for e in check_voices.check(root)), patch
    vj.unlink()
    assert any("voice.json: немає" in e for e in check_voices.check(root))
    shutil.copytree(root / "voices/alice", root / "voices/Bad_Name")
    assert any("некоректний нікнейм" in e for e in check_voices.check(root))
    (root / "data/inventory-units.csv").unlink()
    assert any("inventory" in e for e in check_voices.check(root))


# ---------------------------------------------------------------- вибір і розв'язання
def three(tmp_path):
    root = mkroot(tmp_path)
    pub(root, "alice", 300)
    pub(root, "bob", 500, LINES[:3])                                      # у bob немає footman
    record(root, 440, [LINES[0], LINES[1]])                               # local: лише peon
    return root


def test_choice_resolution_order_and_fallback(tmp_path):
    root = three(tmp_path)
    assert voices.load_choice(root)["default"] == ["local"]
    assert set(voices.resolve(root)) == {"Units/orc/peon/peonyes1.wav", "Units/orc/peon/peonwhat1.wav"}   # лише local
    voices.save_choice(root, {"default": ["bob", "alice", "local"]})
    r = voices.resolve(root)
    assert {k: v.author for k, v in r.items()} == {
        "Units/orc/peon/peonyes1.wav": "bob", "Units/orc/peon/peonwhat1.wav": "bob", "Units/orc/grunt/gruntyes1.wav": "bob",
        "Units/human/footman/footmanyes1.wav": "alice"}                  # footman у bob немає → наступний, але це не «явний» fallback
    assert not any(p.fallback for p in r.values())
    voices.save_choice(root, {"race": {"orc": "alice"}, "unit": {"orc/peon": "local"},
                              "line": {"Units/orc/peon/peonwhat1.wav": "bob"}})
    r = voices.resolve(root)
    assert r["Units/orc/grunt/gruntyes1.wav"].author == "alice"          # раса
    assert r["Units/orc/peon/peonyes1.wav"].author == "local"            # юніт > раса
    assert r["Units/orc/peon/peonwhat1.wav"].author == "bob"             # рядок > юніт
    assert sorted(r["Units/orc/peon/peonyes1.wav"].alts) == ["alice", "bob", "local"]
    voices.save_choice(root, {"race": {"human": "bob"}})                  # bob не має footman → запасний за default
    p = voices.resolve(root)["Units/human/footman/footmanyes1.wav"]
    assert (p.author, p.wanted, p.fallback) == ("alice", "bob", True)
    voices.save_choice(root, {"race": {"human": None}, "line": {}, "unit": {}})
    assert voices.load_choice(root)["race"] == {}          # розділ замінюється цілком


def test_save_choice_validation(tmp_path):
    root = three(tmp_path)
    for bad in ({"default": ["nobody"]}, {"default": ["bob", "bob"]}, {"race": {"orc": "ghost"}}, {"race": {"Orc!": "bob"}},
                {"unit": {"orc": "bob"}}, {"line": {"../x.wav": "bob"}}, {"line": {"Units/x.wav": "bob"}}, {"race": []},
                {"default": "bob"}, "x", {"race": {"orc": 5}}):
        with pytest.raises(voices.VoiceError):
            voices.save_choice(root, bad)
    assert voices.load_choice(root) == {"default": ["local"], "race": {}, "unit": {}, "line": {}}
    (root / voices.CHOICE_REL).parent.mkdir(parents=True, exist_ok=True)
    (root / voices.CHOICE_REL).write_text("[1")                           # зіпсований файл → типове
    assert voices.load_choice(root)["default"] == ["local"]
    assert voices.set_nickname(root, "carol") == "carol" and voices.get_nickname(root) == "carol"
    with pytest.raises(voices.VoiceError):
        voices.set_nickname(root, "a@b.c")


def test_author_path_rejects_tampered_and_unknown(tmp_path):
    root = three(tmp_path)
    rel = "Units/orc/peon/peonyes1.wav"
    f = root / "voices/bob/units/orc/peon/peonyes1.flac"
    assert voices.author_path(root, "bob", rel) == f
    for a, r in (("bob", "Units/orc/peon/nope.wav"), ("ghost", rel), ("bob", "../../etc/passwd"), ("local", "../x.wav")):
        assert voices.author_path(root, a, r) is None
    f.write_bytes(f.read_bytes() + b"x")
    assert voices.author_path(root, "bob", rel) is None


# ---------------------------------------------------------------- встановлення суміші
def test_install_mix_of_authors_into_temp_game(tmp_path):
    root = mkroot(tmp_path)
    orig = {}
    for nick, freq in (("alice", 300), ("bob", 500)):
        pub(root, nick, freq)
        orig[nick] = {x: pcm(root / f"game-files/Units/{x}.wav") for x in LINES}
    record(root, 440, [LINES[0]])                                         # local: лише peonyes1
    orig["local"] = {LINES[0]: pcm(root / f"game-files/Units/{LINES[0]}.wav")}
    voices.save_choice(root, {"default": ["local", "alice"], "unit": {"orc/grunt": "bob"},
                              "line": {"Units/orc/peon/peonwhat1.wav": "bob"}})
    game = tmp_path / "game"
    (game / "Units").mkdir(parents=True)
    pl = iv.plan(game, root)
    who = {f["rel"]: (f["author"], f["fallback"]) for f in pl["files"]}
    assert who == {"Units/orc/peon/peonyes1.wav": ("local", False), "Units/orc/peon/peonwhat1.wav": ("bob", False),
                   "Units/orc/grunt/gruntyes1.wav": ("bob", False), "Units/human/footman/footmanyes1.wav": ("alice", False)}
    res = iv.apply(game, root)
    assert res["installed"] == 4
    want = {LINES[0]: "local", LINES[1]: "bob", LINES[2]: "bob", LINES[3]: "alice"}
    for x, a in want.items():
        got = pcm(game / f"Units/{x}.wav")
        assert got == orig[a][x], x                                       # байти PCM після FLAC→wav збігаються з оригіналом
    assert iv.apply(game, root)["installed"] == 0                         # повторно — без змін (sha декодованого)
    assert iv.plan(game, root)["same"] == 4
    iv.uninstall(game)
    assert not list((game / "Units").rglob("*.wav"))
    with pytest.raises(iv.InstallError):
        iv.plan(game, tmp_path / "empty-root")


def test_install_cli_plan_shows_author(tmp_path, monkeypatch, capsys):
    root = three(tmp_path)
    voices.save_choice(root, {"default": ["bob", "local"]})
    game = tmp_path / "game"
    game.mkdir()
    monkeypatch.setattr(iv, "ROOT", root)
    monkeypatch.setattr(iv, "GAME", game)
    assert iv.main([]) == 0
    assert "← bob" in capsys.readouterr().out


# ---------------------------------------------------------------- API
@pytest.fixture
def api(svc, tmp_path, monkeypatch):
    (tmp_path / "game").mkdir()
    monkeypatch.setattr(iv, "ROOT", TMP_ROOT)          # інші тести перезавантажують install_voices з власним коренем
    monkeypatch.setattr(iv, "GAME", tmp_path / "game")
    import threading

    from studio.server import serve
    httpd = serve(0, open_browser=False, svc=svc)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    port = httpd.server_address[1]

    def call(method, path, body=None, headers=None):
        c = http.client.HTTPConnection("127.0.0.1", port)
        h = {"X-Studio": "1", **(headers or {})}
        c.request(method, path, body=json.dumps(body) if body is not None else None, headers=h)
        r = c.getresponse()
        raw = r.read()
        c.close()
        return r.status, (json.loads(raw) if r.getheader("Content-Type", "").startswith("application/json") else raw)

    yield call
    httpd.shutdown()


def test_api_voices_flow(api):
    record(TMP_ROOT, 440, LINES[:2])
    st, v = api("GET", "/api/voices")
    assert st == 200 and [a["id"] for a in v["authors"]] == ["local"] and v["authors"][0]["coverage"]["orc"]["peon"] == 2
    assert v["choice"]["default"] == ["local"] and v["nickname"] == ""
    assert api("POST", "/api/voices/publish", {"nickname": "alice", "consent": False})[0] == 400
    assert api("POST", "/api/voices/publish", {"nickname": "a@b.c", "consent": True})[0] == 400
    assert api("POST", "/api/voices/publish", {"consent": True})[0] == 400                  # нікнейму немає ніде
    st, r = api("POST", "/api/voices/publish", {"nickname": "alice", "consent": True})
    assert st == 200 and r["added"] == 2 and r["git"]
    st, v = api("GET", "/api/voices")
    assert [a["id"] for a in v["authors"]] == ["local", "alice"] and v["nickname"] == "alice"       # нік запам'ятовано
    assert v["authors"][1]["license"] == "CC BY 4.0" and v["authors"][1]["files"] == 2
    assert (TMP_ROOT / "data/studio/settings-local.json").is_file()

    st, c = api("POST", "/api/voices/choice", {"default": ["alice", "local"], "unit": {"orc/peon": "alice"}})
    assert st == 200 and c["choice"]["default"] == ["alice", "local"]
    assert api("POST", "/api/voices/choice", {"default": ["ghost"]})[0] == 400
    assert api("POST", "/api/voices/choice", {"nickname": "x@y"})[0] == 400
    assert api("POST", "/api/voices/choice", [1])[0] == 400
    assert api("POST", "/api/voices/choice", {"nickname": "carol"})[1]["nickname"] == "carol"
    assert api("POST", "/api/voices/choice", {"unit": {"orc/peon": None}})[1]["choice"]["unit"] == {}
    assert api("POST", "/api/voices/choice", {"default": ["alice"]}, {"X-Studio": "0"})[0] == 403

    rel = "Units/orc/peon/peonyes1.wav"
    for who in ("alice", "local"):
        st, wav = api("GET", f"/audio/voice/{who}/{rel}")
        assert st == 200 and wav[:4] == b"RIFF"
    st, pl = api("GET", "/api/install/plan")
    assert st == 200 and {a["id"] for a in pl["authors"]} == {"local", "alice"} and pl["choice"]["default"] == ["alice", "local"]
    f = pl["races"][0]["units"][0]["files"][0]
    assert f["author"] == "alice" and sorted(f["alts"]) == ["alice", "local"] and not f["fallback"]


def test_api_audio_voice_traversal_and_unknown(api):
    record(TMP_ROOT, 440, LINES[:1])
    voices.publish("alice", "alice", TMP_ROOT, consent=True)
    ok = "Units/orc/peon/peonyes1.wav"
    assert api("GET", f"/audio/voice/alice/{ok}")[0] == 200
    for path in ("/audio/voice/alice/Units/orc/peon/nope.wav", "/audio/voice/ghost/" + ok,
                 "/audio/voice/alice/../../../../etc/passwd", "/audio/voice/alice/%2e%2e/voice.json",
                 "/audio/voice/alice/Units/../../voice.json", "/audio/voice/..%2f/" + ok, "/audio/voice/local/../x.wav",
                 "/audio/voice/alice/units/orc/peon/peonyes1.flac", "/audio/voice/alice", "/audio/voice/"):
        assert api("GET", path)[0] in (400, 404), path
    # підміна FLAC після публікації → sha не збігається → 404
    f = TMP_ROOT / "voices/alice/units/orc/peon/peonyes1.flac"
    f.write_bytes(f.read_bytes() + b"x")
    assert api("GET", f"/audio/voice/alice/{ok}")[0] == 404


# ---------------------------------------------------------------- оригінали Blizzard і ШІ-дублі
def test_publish_skips_originals_and_check_catches_them(tmp_path):
    root = mkroot(tmp_path)
    pub(root)
    rel = "Units/orc/peon/peonyes1.wav"
    assert rel in json.loads((root / "voices/alice/manifest.json").read_text())
    # користувач залишив оригінал: той самий файл тепер у .originals.json
    (root / "game-files/.originals.json").write_text(json.dumps({rel: {"lang": "ru", "sha256": voices.sha256(root / "game-files" / rel)}}))
    assert any("збігається з оригіналом" in e for e in check_voices.check(root))      # уже опублікований — CI падає
    r = voices.publish("alice", "alice", root, consent=True)
    assert r["removed"] == 1 and rel in {s["rel"] for s in r["skipped"]}             # publish прибирає й пропускає
    assert rel not in json.loads((root / "voices/alice/manifest.json").read_text())
    assert not (root / "voices/alice/units/orc/peon/peonyes1.flac").exists()
    assert check_voices.check(root) == []
    (root / "game-files" / rel).unlink()                                            # файлу локально немає — перевірити неможливо
    assert check_voices.check(root) == []


def test_ai_takes_marked_in_manifest(tmp_path):
    root = mkroot(tmp_path)
    record(root, 440)
    (root / "data/studio").mkdir(parents=True)
    (root / "data/studio/units-orc.json").write_text(json.dumps({"version": 3, "groups": {"peon": {
        "peonyes1.wav": {"approved": "peonyes1.take2.wav", "takes": [
            {"file": "peonyes1.take1.wav"}, {"file": "peonyes1.take2.wav", "source": "ai"}]},
        "peonwhat1.wav": {"approved": "peonwhat1.take1.wav", "takes": [{"file": "peonwhat1.take1.wav"}]}}}}))
    voices.publish("alice", "alice", root, consent=True)
    man = json.loads((root / "voices/alice/manifest.json").read_text())
    assert man["Units/orc/peon/peonyes1.wav"]["ai"] is True and "ai" not in man["Units/orc/peon/peonwhat1.wav"]
    assert voices.author_info(root, "alice")["ai"] == 1 and check_voices.check(root) == []
    man["Units/orc/peon/peonwhat1.wav"]["ai"] = "yes"
    (root / "voices/alice/manifest.json").write_text(json.dumps(man))
    assert any("ai у manifest" in e for e in check_voices.check(root))


def test_publish_normalizes_case_of_game_dirs(tmp_path):
    """Студія може писати game-files/Units/Orc/… — пакет і маніфест мусять мати канонічний «Units/orc/…» і пройти перевірку."""
    root = mkroot(tmp_path)
    for x in LINES:
        race, rest = x.split("/", 1)
        synth(root / f"game-files/Units/{race.capitalize()}/{rest}.wav", freq=440)
    voices.publish("alice", "alice", root, consent=True)
    keys = set(voices.manifest(root, "alice"))
    assert keys == {f"Units/{x}.wav" for x in LINES}
    assert all(p.relative_to(root / "voices/alice").as_posix() == p.relative_to(root / "voices/alice").as_posix().lower()
               for p in (root / "voices/alice/units").rglob("*.flac"))
    assert check_voices.check(root) == []


def test_check_ignores_os_junk_files(tmp_path):
    """Finder/Провідник кладуть .DS_Store, Thumbs.db, desktop.ini — це не «сторонні файли» пакета."""
    root = mkroot(tmp_path)
    pub(root)
    for junk in (root / "voices/.DS_Store", root / "voices/alice/Thumbs.db", root / "voices/alice/units/orc/desktop.ini"):
        junk.write_bytes(b"x")
    assert check_voices.check(root) == []
