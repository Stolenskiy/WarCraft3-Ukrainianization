"""tools/install_voices.py на тимчасовій «грі»: план, встановлення, бекап чужого, симлінк у Mods, відкат."""
import importlib
import os

from conftest import synth


def test_install_and_uninstall(tmp_path, monkeypatch):
    root, game = tmp_path / "repo", tmp_path / "game"
    synth(root / "game-files/Units/orc/peon/peonyes1.wav")
    synth(root / "game-files/Units/orc/peon/peonwhat1.wav", freq=300)
    synth(root / "game-files/Units/orc/grunt/gruntyes1.wav")
    (game / "Units/orc/peon").mkdir(parents=True)
    (game / "Units/orc/peon/peonwhat1.wav").write_bytes(b"ORIGINAL")         # чужий файл
    (game / "Mods/grunt").mkdir(parents=True)
    os.symlink(game / "Mods/grunt", game / "Units/orc/grunt")                  # як у репаку
    monkeypatch.setenv("WC3UA_ROOT", str(root))
    monkeypatch.setenv("WC3_GAME_ROOT", str(game))
    import install_voices as iv
    iv = importlib.reload(iv)

    assert iv.main([]) == 0 and not (game / "Units/orc/peon/peonyes1.wav").exists()   # план
    assert iv.main(["--apply"]) == 0
    assert (game / "Units/orc/peon/peonyes1.wav").read_bytes()[:4] == b"RIFF"
    assert (game / "Backups/ua-voices/originals/Units/orc/peon/peonwhat1.wav").read_bytes() == b"ORIGINAL"
    assert not list((game / "Mods/grunt").iterdir())                            # крізь симлінк — ні
    assert iv.main(["--apply"]) == 0                                            # повторно — без змін

    assert iv.main(["--uninstall"]) == 0
    assert not (game / "Units/orc/peon/peonyes1.wav").exists()
    assert (game / "Units/orc/peon/peonwhat1.wav").read_bytes() == b"ORIGINAL"
    assert "ROLLBACK" in (game / "Backups/ua-voices/CHANGE-LOG.txt").read_text()


# ---------------------------------------------------------------- матеріалізація симлінків юнітів
import hashlib  # noqa: E402
import json  # noqa: E402
import threading  # noqa: E402
import urllib.error  # noqa: E402
import urllib.request  # noqa: E402

import pytest  # noqa: E402


def _tree(d):
    """Знімок теки: відносний шлях → (тип, sha256 або readlink)."""
    out = {}
    for p in sorted(d.rglob("*")):
        rel = p.relative_to(d).as_posix()
        out[rel] = ("link", os.readlink(p)) if p.is_symlink() else (
            ("dir", "") if p.is_dir() else ("file", hashlib.sha256(p.read_bytes()).hexdigest()))
    return out


@pytest.fixture
def world(tmp_path, monkeypatch):
    root, game = tmp_path / "repo", tmp_path / "game"
    synth(root / "game-files/Units/orc/grunt/gruntyes1.wav")
    synth(root / "game-files/Units/orc/grunt/gruntwhat1.wav", freq=300)
    synth(root / "game-files/Units/orc/peon/peonyes1.wav")
    mods = game / "Mods/Reforged Models/units/orc/grunt"
    mods.mkdir(parents=True)
    (mods / "grunt.mdx").write_bytes(b"MODEL")
    (mods / "grunt_diffuse.blp").write_bytes(b"TEX")
    (game / "Units/orc/peon").mkdir(parents=True)
    os.symlink("../../Mods/Reforged Models/units/orc/grunt", game / "Units/orc/grunt")   # відносний, як у репаку
    monkeypatch.setenv("WC3UA_ROOT", str(root))
    monkeypatch.setenv("WC3_GAME_ROOT", str(game))
    import install_voices as iv
    return importlib.reload(iv), root, game


def test_plan_lists_materialization_and_changes_nothing(world):
    iv, root, game = world
    before = _tree(game)
    pl = iv.plan(game, root)
    assert [m["rel"] for m in pl["materialize"]] == ["Units/orc/grunt"]
    assert pl["materialize"][0]["entries"] == 2 and pl["materialize"][0]["link"].startswith("../../Mods/")
    assert {c["rel"] for c in pl["copy"]} == {"Units/orc/grunt/gruntyes1.wav", "Units/orc/grunt/gruntwhat1.wav",
                                              "Units/orc/peon/peonyes1.wav"}
    assert pl["skipped"] == [] and _tree(game) == before


def test_materialize_install_uninstall_roundtrip(world):
    iv, root, game = world
    mods_before = _tree(game / "Mods")
    link_before = os.readlink(game / "Units/orc/grunt")
    res = iv.apply(game, root)
    g = game / "Units/orc/grunt"
    assert res["materialized"] == ["Units/orc/grunt"] and res["installed"] == 3
    assert g.is_dir() and not g.is_symlink()
    orig = game / "Mods/Reforged Models/units/orc/grunt"
    for n in ("grunt.mdx", "grunt_diffuse.blp"):
        assert (g / n).is_symlink() and os.path.isabs(os.readlink(g / n))
        assert os.readlink(g / n) == str(orig / n) and (g / n).read_bytes() == (orig / n).read_bytes()
    w = g / "gruntyes1.wav"
    assert w.is_file() and not w.is_symlink() and w.read_bytes()[:4] == b"RIFF"
    assert os.path.realpath(w).startswith(os.path.realpath(g))
    assert _tree(game / "Mods") == mods_before                          # Mods: байт у байт
    man = json.loads((game / "Backups/ua-voices/manifest.json").read_text())
    assert man["materialized"]["Units/orc/grunt"]["link_target"] == link_before
    log = (game / "Backups/ua-voices/CHANGE-LOG.txt").read_text()
    assert "ROLLBACK" in log and "MATERIALIZED Units/orc/grunt" in log and link_before in log

    snap = _tree(game)
    res2 = iv.apply(game, root)                                          # ідемпотентно
    assert res2["installed"] == 0 and res2["materialized"] == [] and res2["unchanged"] == 3
    assert {k: v for k, v in _tree(game).items() if not k.startswith("Backups/")} == \
           {k: v for k, v in snap.items() if not k.startswith("Backups/")}
    assert len(list(g.iterdir())) == 4

    un = iv.uninstall(game)
    assert un["restored_links"] == ["Units/orc/grunt"]
    assert (game / "Units/orc/grunt").is_symlink() and os.readlink(game / "Units/orc/grunt") == link_before
    assert not (game / "Units/orc/peon/peonyes1.wav").exists()
    assert _tree(game / "Mods") == mods_before
    assert json.loads((game / "Backups/ua-voices/manifest.json").read_text()) == {"files": {}, "materialized": {}}


def test_uninstall_keeps_dir_with_foreign_files(world):
    iv, root, game = world
    iv.apply(game, root)
    (game / "Units/orc/grunt/mine.txt").write_text("x")
    un = iv.uninstall(game)
    g = game / "Units/orc/grunt"
    assert un["restored_links"] == [] and g.is_dir() and not g.is_symlink() and (g / "mine.txt").exists()
    assert not (g / "gruntyes1.wav").exists() and (g / "grunt.mdx").is_symlink()
    assert "Units/orc/grunt" in json.loads((game / "Backups/ua-voices/manifest.json").read_text())["materialized"]


def test_never_writes_into_mods_or_data(world):
    iv, root, game = world
    (game / "Data").mkdir()
    synth(root / "game-files/Units/orc/shaman/shamanyes1.wav")
    os.symlink("../../Data", game / "Units/orc/shaman")                    # веде в Data/ — у ній нічого не пишемо
    synth(root / "game-files/Units/orc/deep/sub/x.wav")
    os.symlink("../../Mods", game / "Units/orc/deep")                      # симлінк-предок не безпосередній
    pl = iv.plan(game, root)
    assert {s["rel"] for s in pl["skipped"]} == {"Units/orc/deep/sub/x.wav"}
    snap = _tree(game / "Data"), _tree(game / "Mods")
    iv.apply(game, root)
    assert (_tree(game / "Data"), _tree(game / "Mods")) == snap            # жодного байта в Data/ і Mods/
    assert (game / "Units/orc/shaman/shamanyes1.wav").is_file()
    assert not (game / "Data/shamanyes1.wav").exists() and not list((game / "Data").iterdir())
    assert not (game / "Mods/sub").exists()


def test_install_replacing_entry_in_materialized_dir_restores_link(world):
    iv, root, game = world
    (game / "Mods/Reforged Models/units/orc/grunt/gruntyes1.wav").write_bytes(b"MODS-WAV")   # елемент-симлінк із тим же ім'ям
    mods_before = _tree(game / "Mods")
    iv.apply(game, root)
    assert (game / "Units/orc/grunt/gruntyes1.wav").read_bytes()[:4] == b"RIFF"
    iv.uninstall(game)
    assert os.readlink(game / "Units/orc/grunt").startswith("../../Mods") and _tree(game / "Mods") == mods_before


def test_cli_plan_apply_uninstall(world, capsys):
    iv, root, game = world
    assert iv.main([]) == 0 and "МАТЕРІАЛІЗУЮ Units/orc/grunt" in capsys.readouterr().out
    assert iv.main(["--apply"]) == 0 and (game / "Units/orc/grunt").is_dir()
    assert iv.main(["--uninstall"]) == 0 and (game / "Units/orc/grunt").is_symlink()


def test_empty_game_files_and_missing_game(world, tmp_path):
    iv, root, game = world
    with pytest.raises(iv.InstallError):
        iv.plan(tmp_path / "nope", root)
    with pytest.raises(iv.InstallError):
        iv.plan(game, tmp_path / "emptyroot")


def test_old_flat_manifest_still_uninstalls(world):
    iv, root, game = world
    iv.apply(game, root)
    mp = game / "Backups/ua-voices/manifest.json"
    man = json.loads(mp.read_text())
    mp.write_text(json.dumps(man["files"]))                                # формат до матеріалізації
    iv.uninstall(game)
    assert not (game / "Units/orc/peon/peonyes1.wav").exists()


# ---------------------------------------------------------------- API студії
def test_studio_install_api(world, monkeypatch):
    iv, root, game = world
    import studio.server as srv
    from studio import core
    from studio.server import serve
    monkeypatch.setattr(srv.install_voices, "GAME", game)
    monkeypatch.setattr(srv.install_voices, "ROOT", root)
    httpd = serve(0, open_browser=False, svc=core.Service())
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"

    def call(path, post=False, headers=None):
        h = {"X-Studio": "1", **(headers or {})} if post else {}
        req = urllib.request.Request(base + path, data=b"{}" if post else None, headers=h, method="POST" if post else "GET")
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())
    try:
        mods_before = _tree(game / "Mods")
        code, pl = call("/api/install/plan")
        assert code == 200 and pl["materialize"][0]["rel"] == "Units/orc/grunt" and (game / "Units/orc/grunt").is_symlink()
        assert call("/api/install", post=True, headers={"X-Studio": "0"})[0] == 403          # захист POST
        assert call("/api/install", post=True, headers={"Origin": "http://evil.example"})[0] == 403
        assert (game / "Units/orc/grunt").is_symlink()
        code, res = call("/api/install", post=True)
        assert code == 200 and res["installed"] == 3 and res["materialized"] == ["Units/orc/grunt"]
        assert (game / "Units/orc/grunt").is_dir() and not (game / "Units/orc/grunt").is_symlink()
        code, res = call("/api/uninstall", post=True)
        assert code == 200 and res["restored_links"] == ["Units/orc/grunt"] and (game / "Units/orc/grunt").is_symlink()
        assert _tree(game / "Mods") == mods_before
        monkeypatch.setattr(srv.install_voices, "GAME", game / "nope")
        assert call("/api/install/plan")[0] == 400
    finally:
        httpd.shutdown()
