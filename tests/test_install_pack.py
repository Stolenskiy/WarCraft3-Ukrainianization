"""tools/install_pack.py на тимчасовій «грі»: сухий прогін, встановлення, відкат, збій посеред запису, цілі, CLI."""
import json
import os
import shutil
from pathlib import Path

import install_pack as ip
import pytest
import test_textpack as ttp
import textpack as tp

K = ttp.K


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("WC3UA_ROOT", str(tmp_path / "repo"))
    n = ttp.Net()
    monkeypatch.setattr(tp, "http_json", n.json)
    monkeypatch.setattr(tp, "http_download", n.download)
    game = tmp_path / "game"
    (game / "Units").mkdir(parents=True)
    (game / "Units/HumanUnitStrings.txt").write_bytes(b"ORIGINAL")           # регістр CASC-імені
    (game / "Units/UnitUI.slk").write_bytes(b"KEEP")
    tpl = ttp.own_fdf(tmp_path / "tpl")
    fonts = tmp_path / "fonts"
    fonts.mkdir()
    (fonts / "frizqt__.ttf").write_bytes(b"CYR")
    return game, tpl, fonts, n


def kw(world):
    game, tpl, fonts, _ = world
    return {"game": game, "fdf_template": tpl, "fonts_from": fonts, "out": lambda *_: None}


def snapshot(d: Path):
    return {p.relative_to(d).as_posix(): p.read_bytes() for p in sorted(d.rglob("*")) if p.is_file() and "Backups" not in p.parts}


def test_dry_run_writes_nothing(world, capsys):
    game = world[0]
    before = snapshot(game)
    lines = []
    assert ip.run("classic-1.31", ["text"], **{**kw(world), "out": lines.append}) == 0
    assert snapshot(game) == before and not (game / "Backups").exists()
    text = "\n".join(lines)
    assert "коміт upstream aaaaaaaaaa" in text and "гарячі клавіші: маркерів додано 2" in text and "Це план" in text


def test_apply_backup_case_changelog_idempotent_and_rollback(world):
    game = world[0]
    before = snapshot(game)
    assert ip.run("classic-1.31", ["text"], apply=True, **kw(world)) == 0
    # регістр існуючого файлу збережено, чужий вміст у бекапі, клавіші додано
    assert not (game / "Units/humanunitstrings.txt").exists() or os.path.samefile(game / "Units/humanunitstrings.txt", game / "Units/HumanUnitStrings.txt")
    assert f"({K}P|r)" in (game / "Units/HumanUnitStrings.txt").read_text(encoding="utf-8")
    assert (game / "Backups/ua-text/originals/Units/HumanUnitStrings.txt").read_bytes() == b"ORIGINAL"
    assert (game / "fonts/frizqt__.ttf").read_bytes() == b"CYR" and (game / "UI/framedef/globalstrings.fdf").is_file()
    log = (game / "Backups/ua-text/CHANGE-LOG.txt").read_text(encoding="utf-8")
    assert "commit=" + "a" * 40 in log and "archive_sha256=" in log and "ROLLBACK: python tools/run.py uninstall --target classic-1.31" in log
    man = json.loads((game / "Backups/ua-text/manifest.json").read_text(encoding="utf-8"))
    assert man["source"]["commit"] == "a" * 40
    after = snapshot(game)
    assert ip.run("classic-1.31", ["text"], apply=True, **kw(world)) == 0 and snapshot(game) == after      # ідемпотентно
    assert ip.run_uninstall("classic-1.31", ["text"], game=game, out=lambda *_: None) == 0
    assert snapshot(game) == before                                                                      # байт-у-байт як було


def test_failure_midway_rolls_back(world, monkeypatch):
    game = world[0]
    before = snapshot(game)
    real, n = shutil.copy2, {"i": 0}

    def flaky(src, dst, **k):
        n["i"] += 1
        if n["i"] == 4:
            raise OSError("disk full")
        return real(src, dst, **k)
    monkeypatch.setattr(ip.shutil, "copy2", flaky)
    lines = []
    assert ip.run("classic-1.31", ["text"], apply=True, **{**kw(world), "out": lines.append}) == 1
    monkeypatch.setattr(ip.shutil, "copy2", real)
    assert any("відкочено" in x for x in lines)
    assert snapshot(game) == before and not (game / "Backups/ua-text/manifest.json").exists()


def test_changed_by_user_file_not_removed_on_uninstall(world):
    game = world[0]
    ip.run("classic-1.31", ["text"], apply=True, **kw(world))
    (game / "Units/commandstrings.txt").write_bytes(b"USER EDIT")
    ip.run_uninstall("classic-1.31", ["text"], game=game, out=lambda *_: None)
    assert (game / "Units/commandstrings.txt").read_bytes() == b"USER EDIT"
    assert (game / "Units/HumanUnitStrings.txt").read_bytes() == b"ORIGINAL"


def test_symlinked_dir_is_materialized_and_restored_and_mods_untouched(world):
    game = world[0]
    (game / "Mods/pkg/UI").mkdir(parents=True)
    (game / "Mods/pkg/UI/orig.txt").write_text("m")
    os.symlink(game / "Mods/pkg/UI", game / "UI")
    mods = snapshot(game / "Mods")
    ip.run("classic-1.31", ["text"], apply=True, **kw(world))
    assert snapshot(game / "Mods") == mods and not (game / "UI").is_symlink() and (game / "UI/tipstrings.txt").is_file()
    assert (game / "UI/orig.txt").is_symlink()
    ip.run_uninstall("classic-1.31", ["text"], game=game, out=lambda *_: None)
    assert (game / "UI").is_symlink() and snapshot(game / "Mods") == mods


def test_target_layout_reforged_uses_retail_subdir(world, tmp_path):
    game = world[0]
    lines = []
    assert ip.run("reforged", ["text"], **{**kw(world), "out": lines.append}) == 1 and "_retail_" in "\n".join(lines)
    (game / "_retail_").mkdir()
    assert ip.run("reforged", ["text"], apply=True, **kw(world)) == 0
    assert (game / "_retail_/Units/commandstrings.txt").read_bytes() == ttp.FILES["Units/commandstrings.txt"]     # без клавіш
    assert (game / "_retail_/fonts/frizqt__.ttf").read_bytes() == b"FONT" and not (game / "Backups").exists()
    assert (game / "_retail_/Backups/ua-text/manifest.json").is_file()
    assert not (game / "Units/commandstrings.txt").exists()


def test_legacy_target_root_is_game_and_skips_skin_files(world):
    game = world[0]
    assert ip.run("legacy", ["text"], apply=True, **kw(world)) == 0
    assert f"({K}A|r)" in (game / "Units/commandstrings.txt").read_text(encoding="utf-8")
    assert not (game / "Units/unitskinstrings.txt").exists() and not (game / "doodads").exists()


def test_voice_part_without_picks_does_not_fail(world, monkeypatch):
    lines = []
    monkeypatch.setattr(ip.iv, "plan", lambda root: (_ for _ in ()).throw(ip.iv.InstallError("немає що встановлювати")))
    assert ip.run("classic-1.31", ["voice"], **{**kw(world), "out": lines.append}) == 0
    assert any("ГОЛОС: пропущено" in x for x in lines)


def test_voice_experimental_warning_and_root(world, monkeypatch):
    game = world[0]
    (game / "_retail_").mkdir()
    seen, lines = [], []
    monkeypatch.setattr(ip.iv, "plan", lambda root: seen.append(root) or {"files": [], "same": 0, "materialize": [], "skipped": []})
    assert ip.run("reforged", ["voice"], **{**kw(world), "out": lines.append}) == 0
    assert seen == [game / "_retail_"] and any("ЕКСПЕРИМЕНТАЛЬНО" in x for x in lines)


def test_bad_part_and_layout_drift_exit_codes(world):
    assert ip.run("classic-1.31", ["audio"], **kw(world)) == 2
    world[3].files = {"Units/x.md": b"x"}
    lines = []
    assert ip.run("classic-1.31", ["text"], apply=True, **{**kw(world), "out": lines.append}) == 1
    assert not (world[0] / "Backups").exists() and any("ПОМИЛКА" in x for x in lines)      # нічого не записано


def test_cli_main_and_run_py_wiring(world, monkeypatch):
    import run
    monkeypatch.setenv("WC3_GAME_ROOT", str(world[0]))
    assert ip.main(["install", "--target", "classic-1.31", "--parts", "text", "--fdf-template", str(world[1])]) == 0
    got = []
    monkeypatch.setattr(run, "_call", lambda cmd: got.append(cmd) or 0)
    run.main(["install", "--target", "reforged", "--parts", "text", "--full", "--ref", "abc", "--apply"])
    run.main(["uninstall", "--target", "legacy", "--parts", "text"])
    assert got[0][-9:] == ["install", "--target", "reforged", "--parts", "text", "--full", "--ref", "abc", "--apply"]
    assert got[1][-5:] == ["uninstall", "--target", "legacy", "--parts", "text"][-5:]
