"""Windows/Linux-гілки без справжньої Windows: doctor, opener, venv, інсталятор без симлінків (мок platform/winreg/os)."""
import importlib
import os
import sys
import types

import doctor
import opener
import pytest
from conftest import synth


def fake_winreg(value):
    class K:
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    def open_key(hive, path, *_):
        assert path.lower() == r"software\blizzard entertainment\warcraft iii"   # реєстр нечутливий до регістру
        if value is None:
            raise OSError
        return K()

    return types.SimpleNamespace(HKEY_CURRENT_USER=2, HKEY_LOCAL_MACHINE=1, KEY_READ=1, OpenKey=open_key,
                                 QueryValueEx=lambda k, n: (value, 4) if n == "Allow Local Files" else (_ for _ in ()).throw(OSError()))


@pytest.fixture
def win(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(doctor.shutil, "which", lambda c: None)
    for k in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        monkeypatch.setenv(k, str(tmp_path / k))
    monkeypatch.delenv("WC3_GAME_ROOT", raising=False)
    return tmp_path


def rows():
    return {r[0].split(" (")[0]: r for r in doctor.checks()}


def test_venv_python_per_os(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    assert doctor.venv_python().parts[-2:] == ("Scripts", "python.exe")
    monkeypatch.setattr(sys, "platform", "linux")
    assert doctor.venv_python().parts[-2:] == ("bin", "python")


def test_windows_hints(win, monkeypatch):
    monkeypatch.setitem(sys.modules, "winreg", fake_winreg(None))
    r = rows()
    assert "winget" in r["ffmpeg"][3] and "winget" in r["Python 3.11 або uv"][3]
    assert "Google Chrome / Edge + playwright" in r and r["Google Chrome / Edge + playwright"][3]
    reg = r["«Allow Local Files» = 1"][3]
    assert reg.startswith('reg add "HKCU\\Software\\Blizzard Entertainment\\Warcraft III" /v "Allow Local Files" /t REG_DWORD /d 1')


def test_windows_edge_detected_and_registry_ok(win, monkeypatch):
    edge = win / "ProgramFiles(x86)" / "Microsoft/Edge/Application/msedge.exe"
    edge.parent.mkdir(parents=True)
    edge.write_text("x")
    assert edge in doctor.browser_paths()
    monkeypatch.setitem(sys.modules, "winreg", fake_winreg(1))
    assert doctor.allow_local_files() is True
    assert rows()["«Allow Local Files» = 1"][3] == ""
    monkeypatch.setitem(sys.modules, "winreg", fake_winreg(0))
    assert doctor.allow_local_files() is False


def test_windows_registry_missing_is_none(win, monkeypatch):
    monkeypatch.setitem(sys.modules, "winreg", None)
    assert doctor.allow_local_files() is None


def test_linux_has_no_registry_row(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    assert "«Allow Local Files» = 1" not in rows()
    assert "apt install ffmpeg" in rows()["ffmpeg"][3] or rows()["ffmpeg"][3] == ""


def test_opener_per_os(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(opener.subprocess, "run", lambda cmd, **k: calls.append(cmd))
    monkeypatch.setattr(sys, "platform", "darwin")
    assert opener.open_dir(tmp_path) and calls[-1][0] == "open"
    monkeypatch.setattr(sys, "platform", "linux")
    assert opener.open_dir(tmp_path) and calls[-1][0] == "xdg-open"
    started = []
    monkeypatch.setattr(os, "startfile", started.append, raising=False)
    monkeypatch.setattr(sys, "platform", "win32")
    assert opener.open_dir(tmp_path) and started == [str(tmp_path)]


def test_opener_without_gui_returns_false(monkeypatch, tmp_path):
    def boom(*a, **k):
        raise FileNotFoundError
    monkeypatch.setattr(opener.subprocess, "run", boom)
    monkeypatch.setattr(sys, "platform", "linux")
    assert opener.open_dir(tmp_path) is False


def _world(tmp_path, monkeypatch):
    root, game = tmp_path / "repo", tmp_path / "game"
    synth(root / "game-files/Units/orc/peon/peonyes1.wav")
    synth(root / "game-files/Units/orc/grunt/gruntyes1.wav")
    (game / "Units/orc/peon").mkdir(parents=True)          # звичайні теки, без жодного симлінка (типовий Windows)
    (game / "Units/orc/grunt").mkdir(parents=True)
    (game / "Data").mkdir()
    monkeypatch.setenv("WC3UA_ROOT", str(root))
    monkeypatch.setenv("WC3_GAME_ROOT", str(game))
    import install_voices as iv
    return importlib.reload(iv), root, game


def test_install_without_any_symlinks_and_cyrillic_path(tmp_path, monkeypatch):
    base = tmp_path / "Мій Варкрафт"
    base.mkdir()
    iv, root, game = _world(base, monkeypatch)
    monkeypatch.setattr(os, "symlink", lambda *a, **k: (_ for _ in ()).throw(OSError("WinError 1314")))
    res = iv.apply(game, root)
    assert res["installed"] == 2 and res["materialized"] == []
    assert (game / "Units/orc/grunt/gruntyes1.wav").read_bytes()[:4] == b"RIFF"
    up = iv.uninstall_plan(game)
    assert {f["rel"] for f in up["files"]} == {"Units/orc/grunt/gruntyes1.wav", "Units/orc/peon/peonyes1.wav"}
    assert iv.uninstall(game)["removed"] == 2


def test_materialize_without_symlink_rights_gives_clear_error(tmp_path, monkeypatch):
    iv, root, game = _world(tmp_path, monkeypatch)
    real = game / "Mods/grunt"
    real.mkdir(parents=True)
    (real / "a.mdx").write_text("m")
    (game / "Units/orc/grunt").rmdir()
    os.symlink(real, game / "Units/orc/grunt")
    real_symlink = os.symlink
    monkeypatch.setattr(os, "symlink", lambda *a, **k: (_ for _ in ()).throw(OSError("privilege not held")))
    with pytest.raises(iv.InstallError, match="симлінки"):
        iv.apply(game, root)
    monkeypatch.setattr(os, "symlink", real_symlink)
    assert (game / "Units/orc/grunt").is_symlink() and not (game / "Units/orc/grunt.ua-tmp").exists()
    assert list(real.iterdir()) == [real / "a.mdx"]
