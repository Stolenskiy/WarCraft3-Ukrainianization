"""API «Тека гри»: GET/POST /api/game-root з тимчасовими теками й фейковим коренем WC3 (справжню гру не чіпаємо)."""
import json
from pathlib import Path

import gameconf
import install_voices
import pytest
from test_studio_core import api  # noqa: F401  (фікстура HTTP-клієнта)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.delenv("WC3_GAME_ROOT", raising=False)
    monkeypatch.setenv("WC3UA_ROOT", str(tmp_path / "repo"))
    monkeypatch.setattr(gameconf, "candidates", lambda: [])
    monkeypatch.setattr(install_voices, "GAME", install_voices.GAME)       # відновиться після тесту
    return tmp_path


def fake_game(p: Path) -> Path:
    (p / "Data").mkdir(parents=True)
    return p


def test_get_reports_default_when_nothing_found(env, api):  # noqa: F811
    code, d = api("/api/game-root")
    assert code == 200 and d["valid"] is False and d["source"] == "default" and d["candidates"] == []


def test_set_valid_path_saves_and_updates_install_target(env, api):  # noqa: F811
    game = fake_game(env / "wc3")
    code, d = api("/api/game-root", {"path": str(game)})
    assert code == 200 and d["valid"] and d["source"] == "settings" and d["path"] == str(game)
    assert json.loads((env / "repo/data/local/settings.json").read_text())["game_root"] == str(game)
    assert install_voices.GAME == game                                     # плани бачать нову теку без перезапуску
    assert api("/api/game-root")[1]["path"] == str(game)


def test_set_invalid_path_is_400_and_keeps_state(env, api):  # noqa: F811
    (env / "plain").mkdir()
    code, d = api("/api/game-root", {"path": str(env / "plain")})
    assert code == 400 and "не схоже на теку Warcraft III" in d["error"]
    assert not (env / "repo/data/local/settings.json").exists()
    assert api("/api/game-root", {})[0] == 400                             # без path
    assert api("/api/game-root", {"path": str(env / "plain")}, headers={"X-Studio": "0"})[0] == 403


def test_autodetect_and_clear(env, api, monkeypatch):  # noqa: F811
    assert api("/api/game-root", {"autodetect": True})[0] == 400           # нічого не знайдено
    game = fake_game(env / "auto")
    monkeypatch.setattr(gameconf, "candidates", lambda: [str(game)])
    code, d = api("/api/game-root")
    assert d["candidates"] == [str(game)] and d["source"] == "auto"
    code, d = api("/api/game-root", {"autodetect": True})
    assert code == 200 and d["source"] == "settings" and d["path"] == str(game)
    code, d = api("/api/game-root", {"clear": True})
    assert code == 200 and d["source"] == "auto"


def test_env_override_is_read_only(env, api, monkeypatch):  # noqa: F811
    game = fake_game(env / "envgame")
    monkeypatch.setenv("WC3_GAME_ROOT", str(game))
    code, d = api("/api/game-root")
    assert d["env_overrides"] and d["source"] == "env" and d["valid"]
    code, d = api("/api/game-root", {"path": str(game)})
    assert code == 400 and "WC3_GAME_ROOT" in d["error"]
