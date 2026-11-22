"""Наші правки поверх upstream-текстів Units/*.txt (tools/text_overrides.py, data/text-overrides/units.json)."""
import json

import text_overrides as T

SRC = """// коментар
[ostr]
Name=Тверджа
Ubertip="Дозволить дозволить, будівлі."

[Errors]
Emptycontrolgroup=Порожній.
// кінець без нового рядка"""


def ops(d):
    return T.for_file({"units/x.txt": d}, "Units/X.txt")


def test_replace_append_set_and_insert_missing_key():
    o = ops({"OSTR": {"ubertip": {"replace": [["Дозволить дозволить", "Дозволить"]], "append": "|nсіра?"}},
             "Errors": {"Nonunitincontrolgroup": {"set": "Лише юніти."}},
             "Hkee": {"Tip": {"set": "Фортеця, нова"}}})
    out, n, notes = T.apply(SRC, o, "Units/X.txt")
    assert 'Ubertip="Дозволить, будівлі.|nсіра?"' in out and n == 2 and notes == ["Units/X.txt [hkee] tip: немає в upstream — пропущено"]
    assert "// кінець без нового рядка\nNonunitincontrolgroup=Лише юніти.\n" in out
    assert "[Hkee]" not in out and "Name=Тверджа" in out


def test_missing_targets_reported_not_failing():
    o = ops({"ostr": {"Ubertip": {"replace": [["нема", "є"]]}, "Tip": {"append": "x"}}, "zzzz": {"Name": {"append": "x"}}})
    out, n, notes = T.apply(SRC, o, "Units/X.txt")
    assert 'Ubertip="Дозволить дозволить, будівлі."' in out and n == 1
    assert len(notes) == 3 and any("не знайдено" in x for x in notes) and sum("немає в upstream" in x for x in notes) == 2


def test_unquoted_value_gets_quoted_when_comma_appears_and_noop():
    out, _, _ = T.apply("[a]\nTip=Просто\n", ops({"a": {"Tip": {"append": ", ще"}}}))
    assert out == '[a]\nTip="Просто, ще"\n'
    assert T.apply(SRC, {}) == (SRC, 0, [])


def test_load_and_repo_file(tmp_path):
    assert T.load(tmp_path / "nope.json") == {}
    (tmp_path / "o.json").write_text(json.dumps({"_comment": "x", "Units/A.txt": {"s": {"k": {"set": "v"}}}}))
    assert T.load(tmp_path / "o.json") == {"units/a.txt": {"s": {"k": {"set": "v"}}}}
    repo = T.load()
    assert "units/orcunitstrings.txt" in repo
    for _f, secs in repo.items():                    # лише наші операції; set — короткі власні рядки, не тексти upstream
        for keys in secs.values():
            for op in keys.values():
                assert set(op) <= {"replace", "append", "set"} and len(op.get("set", "")) < 120
