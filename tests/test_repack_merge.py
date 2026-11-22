"""Зведення перекладу Units/*.txt із патчем балансу репаку (tools/repack_merge.py). Дані синтетичні, вигадані."""
import json
from pathlib import Path

import repack_merge as R

UA = {
    "Units/zzabilitystrings.txt": (
        "[Azap]\nName=Розряд\nTip=Розряд (|cffffcc00Z|r)\nUbertip=\"Б'є блискавкою, ціль тремтить.\"\n"
        "\n[Bzap]\nBufftip=Розряд\n"
        "\n[Ahop]\nName=Стрибок\nTip=Стрибок - [|cffffcc00рівень 1|r],Стрибок - [|cffffcc00рівень 2|r]\n"
        "Ubertip=\"Стрибає недалеко.\",\"Стрибає далі.\"\n"
        "\n[Aodd]\nName=Дивина\nUbertip=\"Один рівень.\"\n"
        "\n[Rzap]\nName=Сильний розряд\nUbertip=\"Розряд б'є сильніше.\"\n"),
    "Units/zzunitstrings.txt": "[zgob]\nName=Гоблін\nTip=Найняти гобліна\n\n[zhut]\nName=Хатина",
}
PATCH = {
    "zzabilitystrings.txt": (
        "[Azap]\nName=Zap\nTip=|cffffcc00Z|rap\nUbertip=\"Zaps a target.|n|n|cff99ccffCast Range:|r 600|n|cff99ccffCooldown:|r 5 sec\"\n"
        "Untip=|cffffcc00Z|rap\nUnubertip=\"Zaps a target.|n|n|cff99ccffCast Range:|r 600|n|cff99ccffCooldown:|r 5 sec\"\n"
        "\n[Bzap]\nBufftip=\"Zap\"\nBuffubertip=\"This unit is affected by Zap.|n|n|cffb0b0b0Zap (creep):|r|n|cff99ccffDuration:|r 2 sec\"\n"
        "\n[Ahop]\nName=Hop\nUbertip=\"Hops.|n|n|cff99ccffCooldown:|r 9 sec\",\"Hops far.|n|n|cff99ccffCooldown:|r 7 sec\"\n"
        "\n[Aodd]\nName=Odd\nUbertip=\"One.|n|n|cff99ccffCooldown:|r 1 sec\",\"Two.|n|n|cff99ccffCooldown:|r 2 sec\"\n"
        "\n[Apas]\nName=Zap\nTip=Zap\nUbertip=\"Passive ability. No activation required.|nHas no effect until its research is completed.\"\n"
        "Art=ReplaceableTextures\\x.blp\nResearchtip=Frobnicate the quux\n"
        "\n[Rzap]\nName=Big Zap\nUbertip=\"Zap hits harder.\"\n"),
    "zzunitstrings.txt": (
        "[zgob]\nName=Goblin\nTip=Train Goblin\nUbertip=\"Structure used by this race's economy or army.|n|n"
        "|cffffcc00Attacks land units.|r|n|n|cff99ccffArmor:|r Fortified|n|cff99ccffBuild Time:|r 30 sec\"\n"
        "Description=Melee Ground unit.\n"
        "\n[zhut]\nName=Hut\nTip=Build Hut\nUbertip=\"After research, <Rzap,base1> zaps.\"\n"),
    "zzunitfunc.txt": "[zgob]\nArt=x.blp\n",                                  # не *Strings.txt — ігнорується
}


def patch_dir(root: Path) -> Path:
    d = root / "Warcraft III.app/Contents/Resources/WC3Patcher/data"
    s = d / "patch/Payload/Strings"
    s.mkdir(parents=True)
    for n, t in PATCH.items():
        (s / n).write_text(t, encoding="utf-8")
    (d / "hero_profiles/base").mkdir(parents=True)
    return root


def test_find_sources(tmp_path):
    assert R.find_sources(None) == [] and R.find_sources(tmp_path) == []
    patch_dir(tmp_path / "x86_64")
    got = R.find_sources(tmp_path)
    assert [p.name for p in got] == ["Strings", "base"]


def test_merge_keys_sections_stats(tmp_path):
    patch_dir(tmp_path / "x86_64")
    src = R.find_sources(tmp_path)
    out, st = R.merge(dict(UA), src)
    ab, un = out["Units/zzabilitystrings.txt"], out["Units/zzunitstrings.txt"]
    sec = lambda t, s: R.parse(t)[s.lower()]  # noqa: E731
    # характеристики дописано до наявного опису, мітки й одиниці перекладено
    assert sec(ab, "Azap")["ubertip"] == ('"Б\'є блискавкою, ціль тремтить.|n|n|cff99ccffДальність застосування:|r 600'
                                          '|n|cff99ccffПерезарядка:|r 5 с"')
    # Untip = Tip у патчі → копія нашого Tip; Unubertip — переклад через пам'ять перекладів
    assert sec(ab, "Azap")["untip"] == "Розряд (|cffffcc00Z|r)"
    assert "Б'є блискавкою" in sec(ab, "Azap")["unubertip"] and "Перезарядка" in sec(ab, "Azap")["unubertip"]
    # «This unit is affected by X.» + (creep) у мітці
    assert sec(ab, "Bzap")["buffubertip"].startswith('Цей юніт під дією: Розряд.|n|n|cffb0b0b0Розряд (крип):|r')
    # багаторівневий опис: характеристики по рівнях; різна кількість рівнів — не чіпаємо
    assert sec(ab, "Ahop")["ubertip"] == ('"Стрибає недалеко.|n|n|cff99ccffПерезарядка:|r 9 с",'
                                          '"Стрибає далі.|n|n|cff99ccffПерезарядка:|r 7 с"')
    assert sec(ab, "Aodd")["ubertip"] == '"Один рівень."'
    # нова секція: текстові ключі перекладено, решта — як є; англ. залишок порахований
    apas = sec(ab, "Apas")
    assert apas["ubertip"] == '"Пасивна здібність, активувати не треба.|nНе діє, доки не завершено дослідження."'
    assert apas["name"] == '"Розряд"' and apas["art"] == "ReplaceableTextures\\x.blp"
    assert apas["researchtip"] == '"Frobnicate the quux"'
    # шаблони Train/Build, рядки словничка, тип юніта, «After research» з посиланням
    g, h = sec(un, "zgob"), sec(un, "zhut")
    assert g["tip"] == "Найняти гобліна"                                          # наявне не перекладаємо заново
    assert g["ubertip"] == ('Споруда для економіки чи армії раси.|n|n|cffffcc00Атакує наземні війська.|r|n|n'
                            '|cff99ccffБроня:|r Укріплена|n|cff99ccffЧас будівництва:|r 30 с')
    assert g["description"] == '"Юніт: наземний, ближній бій."'
    assert h["tip"] == "Звести: Хатина"                                         # файл без кінцевого \n
    assert h["ubertip"] == "Після дослідження «Сильний розряд»: Розряд б'є сильніше."
    assert st == {"keys": 7, "sections": 1, "stats": 2, "english": 1, "skipped_sections": 0}
    assert "zzunitfunc.txt" not in str(out)


def test_terms_levels_and_values():
    g = json.loads(R.GLOSSARY.read_text(encoding="utf-8"))
    tr = R.Translator({"a": {"name": "Shock Wave"}}, {"a": {"name": "Хвиля"}}, g)
    assert tr.term("Shockwave") == "Хвиля" and tr.term("Shock Wave.") == "Хвиля."
    assert tr.term("Shock Wave level 2") == "Хвиля, рівень 2" and tr.term("Shock Wave (Trap)") == "Хвиля (пастка)"
    assert tr.term("Nope") is None
    assert tr.line("|cffffcc00Level 3|r") == "|cffffcc00Рівень 3|r"
    assert tr.line("|cff99ccffArmor:|r Heavy") == "|cff99ccffБроня:|r Важка"
    assert tr.line("|cff99ccffUnknown Label:|r 1.5 sec") == "|cff99ccffUnknown Label:|r 1.5 с"
    assert tr.sentence("Summon Golem", "zz") == "Закликати: Golem"
    assert tr.sentence("After research, foo.", "zz") == "After research, foo."
    assert R.levels('"a","b"') == ["a", "b"] and R.levels("x") == ["x"]
    assert not R.english_left("Шкода <AHbz,DataA1> |cffffcc00W|r") and R.english_left("Damage")


def test_glossary_is_clean():
    g = json.loads(R.GLOSSARY.read_text(encoding="utf-8"))
    assert {"labels", "values", "lines", "words"} <= set(g)
    for part in ("labels", "values", "lines", "words"):
        assert all(v and not R.english_left(v) for v in g[part].values()), part


def test_build_merges_when_game_has_patch(tmp_path, monkeypatch):
    import textpack as tp
    up = tmp_path / "up/files"
    for rel, t in UA.items():
        (up / rel).parent.mkdir(parents=True, exist_ok=True)
        (up / rel).write_text(t, encoding="utf-8")
    game = patch_dir(tmp_path / "game/x86_64").parent
    t = tp.load_target("classic-1.31")
    res = tp.build(t, {"files_dir": up, "commit": "c", "variant": "light", "archive_sha256": "s"}, game=game, out=tmp_path / "out")
    assert res.stats["repack"]["keys"] == 7 and res.stats["repack"]["sections"] == 1
    assert "[Apas]" in res.files["Units/zzabilitystrings.txt"].read_text(encoding="utf-8")
    res2 = tp.build(t, {"files_dir": up, "commit": "c", "variant": "light", "archive_sha256": "s"}, out=tmp_path / "out2")
    assert "repack" not in res2.stats
