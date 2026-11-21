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
