"""gameconf: порядок env > settings > автопошук, валідація, гілки Windows/Linux (мок platform/winreg/шляхів)."""
import json
import sys
import types
from pathlib import Path

import gameconf
import pytest


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.delenv("WC3_GAME_ROOT", raising=False)
    monkeypatch.setenv("WC3UA_ROOT", str(tmp_path / "repo"))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
    monkeypatch.setattr(gameconf, "candidates", lambda: [])
    return tmp_path


def fake_game(p: Path) -> Path:
    (p / "Data").mkdir(parents=True)
    return p


def test_looks_like_wc3(tmp_path):
    assert not gameconf.looks_like_wc3(None)
    assert not gameconf.looks_like_wc3(tmp_path / "nope")
    assert not gameconf.looks_like_wc3(tmp_path)
    assert gameconf.looks_like_wc3(fake_game(tmp_path / "a"))
    (tmp_path / "b").mkdir()
    (tmp_path / "b/Warcraft III.exe").write_text("x")
    assert gameconf.looks_like_wc3(tmp_path / "b")


def test_priority_env_settings_auto(env, monkeypatch):
    a, b, c = (fake_game(env / n) for n in "abc")
    monkeypatch.setattr(gameconf, "candidates", lambda: [str(c)])
    assert gameconf.describe()["source"] == "auto" and gameconf.get_game_root() == c
    gameconf.set_game_root(b)
    assert gameconf.describe() == {**gameconf.describe(), "source": "settings", "path": str(b), "valid": True}
    monkeypatch.setenv("WC3_GAME_ROOT", str(a))
    assert gameconf.describe()["source"] == "env" and gameconf.get_game_root() == a


def test_env_invalid_still_wins_but_reported(env, monkeypatch):
    monkeypatch.setenv("WC3_GAME_ROOT", str(env / "missing"))
    d = gameconf.describe()
    assert d["source"] == "env" and d["valid"] is False


def test_default_when_nothing_found(env):
    d = gameconf.describe()
    assert d["source"] == "default" and d["valid"] is False and d["path"]


def test_set_rejects_invalid_and_keeps_file(env):
    with pytest.raises(ValueError):
        gameconf.set_game_root(env / "nothing")
    assert not gameconf.settings_path().exists()
    good = fake_game(env / "g")
    gameconf.set_game_root(good)
    with pytest.raises(ValueError):
        gameconf.set_game_root(env)
    assert json.loads(gameconf.settings_path().read_text())["game_root"] == str(good)


def test_set_keeps_other_keys_and_cyrillic(env):
    f = gameconf.settings_path()
    f.parent.mkdir(parents=True)
    f.write_text('{"x": 1}')
    g = fake_game(env / "Гра Warcraft")
    gameconf.set_game_root(g)
    assert json.loads(f.read_text(encoding="utf-8")) == {"x": 1, "game_root": str(g)}
    assert gameconf.get_game_root() == g


def test_broken_settings_ignored(env):
    f = gameconf.settings_path()
    f.parent.mkdir(parents=True)
    f.write_text("{oops")
    assert gameconf.describe()["source"] == "default"


def test_candidates_macos(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    assert gameconf.candidates() == ["/Applications/Warcraft III Classic", "/Applications/Warcraft III"]
    assert gameconf.default_root() == "/Applications/Warcraft III Classic"


def test_candidates_windows_with_registry(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    reg = types.SimpleNamespace(HKEY_LOCAL_MACHINE=1, HKEY_CURRENT_USER=2, KEY_READ=1, KEY_WOW64_32KEY=2, KEY_WOW64_64KEY=4)

    class K:
        def __init__(self, hive):
            self.hive = hive
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    def open_key(hive, key, _r, _acc):
        if hive != 1:
            raise OSError
        return K(hive)

    reg.OpenKey = open_key
    reg.QueryValueEx = lambda k, name: (r"D:\Games\Warcraft III", 1)
    monkeypatch.setitem(sys.modules, "winreg", reg)
    c = gameconf.candidates()
    assert c[0] == r"D:\Games\Warcraft III" and c.count(c[0]) == 1
    assert c[-2:] == [r"C:\Program Files (x86)\Warcraft III", r"C:\Program Files\Warcraft III"]
    assert gameconf.default_root() == r"C:\Program Files (x86)\Warcraft III"


def test_windows_without_winreg(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setitem(sys.modules, "winreg", None)   # import → ImportError
    assert gameconf.candidates() == gameconf.WIN


def test_linux_wine_prefixes(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.delenv("WINEPREFIX", raising=False)
    wc = fake_game(home / "Games/battlenet/drive_c/Program Files (x86)/Warcraft III")
    wine = fake_game(home / ".wine/drive_c/Program Files/Warcraft III")
    monkeypatch.setenv("WC3UA_ROOT", str(tmp_path / "repo"))
    monkeypatch.delenv("WC3_GAME_ROOT", raising=False)
    assert str(wc) in gameconf.candidates() and str(wine) in gameconf.candidates()
    path, source, valid = gameconf.resolve()
    assert source == "auto" and valid and Path(path) in (wc, wine)
    assert Path(gameconf.default_root()).as_posix().endswith("drive_c/Program Files (x86)/Warcraft III")


def test_linux_custom_wineprefix(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "h"))
    monkeypatch.setenv("WINEPREFIX", str(tmp_path / "pfx"))
    wc = fake_game(tmp_path / "pfx/drive_c/Program Files (x86)/Warcraft III")
    assert str(wc) in gameconf.candidates()


def test_detect_and_clear(env, monkeypatch):
    a, b = fake_game(env / "a"), env / "bad"
    monkeypatch.setattr(gameconf, "candidates", lambda: [str(b), str(a)])
    assert gameconf.detect() == [str(a)]
    gameconf.set_game_root(a)
    gameconf.clear_game_root()
    assert json.loads(gameconf.settings_path().read_text()) == {}
    gameconf.clear_game_root()                                  # повторно — без помилок
    assert gameconf.describe()["source"] == "auto"
