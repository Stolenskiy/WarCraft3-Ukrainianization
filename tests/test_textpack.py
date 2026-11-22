"""tools/textpack.py: гарячі клавіші, FDF 1.31, завантаження upstream (мережа підмінена), кеш, --ref, дрейф розкладу."""
import hashlib
import io
import json
import zipfile
from pathlib import Path

import pytest
import textpack as tp

K = "|cffffcc00"
LIGHT = "LIGHT[Interface only]/_retail_/"
FULL = "FULL[Interface and campaings]/_retail_/"


# ---------------------------------------------------------------- гарячі клавіші
def hk(text):
    return tp.add_hotkey_markers(text)


def test_simple_tip_and_hotkey_untouched():
    out, st = hk("[CmdAttack]\nTip=Атака\nUbertip=\"x, y\"\nHotkey=A\n")
    assert out == f"[CmdAttack]\nTip=Атака ({K}A|r)\nUbertip=\"x, y\"\nHotkey=A\n"
    assert st["markers_added"] == 1 and st["sections_with_hotkey"] == 1 and st["sections_without_markup"] == 1


def test_multilevel_unquoted_and_per_level_keys():
    out, _ = hk("[AHhb]\nTip=Одне,Два,Три\nHotkey=Q,W,E\n")
    assert f"Tip=Одне ({K}Q|r),Два ({K}W|r),Три ({K}E|r)" in out
    out, _ = hk("[AHhb]\nTip=Одне,Два\nHotkey=Q\n")
    assert out.count(f"({K}Q|r)") == 2


def test_quoted_values_keep_quotes_and_inner_commas():
    out, st = hk('[A1]\nTip="Буря, земля - [|cffffcc00рівень 1|r]","Буря, земля - [|cffffcc00рівень 2|r]"\nHotkey=E\n')
    assert out.splitlines()[1] == (f'Tip="Буря, земля - [{K}рівень 1|r] ({K}E|r)","Буря, земля - [{K}рівень 2|r] ({K}E|r)"')
    assert st["markers_added"] == 2                      # розмітка рівнів не вважається «вже з клавішею»


def test_already_marked_and_hint_skipped():
    src = f"[A1]\nTip=Атака ({K}A|r)\nHotkey=A\n[A2]\nTip=Атака ({K}a|r)\nHotkey=A\n[A3]\nUntip=\"|cffc3dbffПКМ|r\"\nUnhotkey=Z\n"
    out, st = hk(src)
    assert out == src and st["skipped_already"] == 3 and st["markers_added"] == 0


def test_research_untip_awaken_revive_variants():
    out, st = hk("[Hpal]\nTip=Паладин\nHotkey=P\nRevivetip=Воскресити паладина\nAwakentip=Воскресити паладина\n"
                 "[AHab]\nResearchtip=\"Аура - [|cffffcc00рівень %d|r]\"\nResearchhotkey=B\nUntip=Вимкнути\nUnhotkey=V\n")
    assert f"Revivetip=Воскресити паладина ({K}P|r)" in out and f"Awakentip=Воскресити паладина ({K}P|r)" in out
    assert f'Researchtip="Аура - [{K}рівень %d|r] ({K}B|r)"' in out
    assert f"Untip=Вимкнути ({K}V|r)" in out and st["markers_added"] == 5
    assert "Hotkey=P\n" in out and "Researchhotkey=B\n" in out and "Unhotkey=V" in out


def test_no_hotkey_no_change_and_bad_key():
    src = "[x]\nTip=Без клавіші\n[y]\nTip=Esc\nHotkey=ESC\n"
    out, st = hk(src)
    assert out == src and st["skipped_badkey"] == 1


def test_bom_crlf_idempotent():
    src = "﻿[a]\r\nTip=Т\r\nHotkey=T\r\n"
    out, _ = hk(src)
    assert out.startswith("﻿") and out == f"﻿[a]\r\nTip=Т ({K}T|r)\r\nHotkey=T\r\n"
    out2, st2 = hk(out)
    assert out2 == out and st2["markers_added"] == 0


def test_split_values_edge_cases():
    assert tp.split_values('"a,b","c"') == ['"a,b"', '"c"']
    assert tp.split_values("a,b,") == ["a", "b", ""]
    assert tp.split_values("") == [""]


# ---------------------------------------------------------------- FDF 1.31
def fdf(path: Path, rows: dict, bom=False, crlf=True):
    nl = "\r\n" if crlf else "\n"
    body = "// c" + nl + "StringList {" + nl + "".join(f'    {k}    "{v}",{nl}' for k, v in rows.items()) + "}" + nl
    path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + body.encode())


def test_build_fdf131_structure_from_template(tmp_path):
    fdf(tmp_path / "t.fdf", {"KEY_A": "Hello", "KEY_B": "Cost %d", "KEY_C": "Only template", "KEY_D": "Spec %s"}, bom=True)
    fdf(tmp_path / "u.fdf", {"KEY_B": "Ціна %d", "KEY_D": "Інше %d", "KEY_A": "Привіт", "KEY_X": "зайвий"})
    rep = tp.build_fdf131(tmp_path / "u.fdf", tmp_path / "t.fdf", tmp_path / "o.fdf", {"KEY_D": "Наше %s"})
    raw = (tmp_path / "o.fdf").read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf") and b"\r\n" in raw and b"KEY_X" not in raw
    ids = [e["id"] for e in tp.fdf_strings.extract(tmp_path / "o.fdf")["entries"]]
    assert ids == ["KEY_A", "KEY_B", "KEY_C", "KEY_D"]            # id і порядок — із шаблону
    vals = {e["id"]: e["value"] for e in tp.fdf_strings.extract(tmp_path / "o.fdf")["entries"]}
    assert vals == {"KEY_A": "Привіт", "KEY_B": "Ціна %d", "KEY_C": "Only template", "KEY_D": "Наше %s"}
    assert rep["missing_in_upstream"] == ["KEY_C"] and rep["format_mismatch"] == []
    rep2 = tp.build_fdf131(tmp_path / "u.fdf", tmp_path / "t.fdf", tmp_path / "o2.fdf")
    assert rep2["format_mismatch"] == ["KEY_D"]


def test_empty_template_is_error(tmp_path):
    (tmp_path / "t.fdf").write_text("nothing", encoding="utf-8")
    fdf(tmp_path / "u.fdf", {"A": "b"})
    with pytest.raises(tp.TextPackError):
        tp.build_fdf131(tmp_path / "u.fdf", tmp_path / "t.fdf", tmp_path / "o.fdf")


# ---------------------------------------------------------------- підроблений upstream
UNITS = "[hpea]\nTip=Селянин\nHotkey=P\n"
FILES = {
    "Units/humanunitstrings.txt": UNITS.encode(),
    "Units/commandstrings.txt": b"[CmdAttack]\nTip=Attack\nHotkey=A\n",
    "Units/unitskinstrings.txt": b"[x]\nName=a\n",
    "UI/tipstrings.txt": b"[Tips]\nTip01=x\n",
    "UI/framedef/globalstrings.fdf": b"",
    "doodads/doodadskinstrings.txt": b"[d]\nName=d\n",
    "fonts/frizqt__.ttf": b"FONT",
    "classic/roc/human01.w3m": b"W3M",
    "movies/captions/a.srt": b"1\n",
    "webui/x.png": b"PNG",
}


def git_sha(b):
    return hashlib.sha1(b"blob %d\0" % len(b) + b).hexdigest()


class Net:
    """Підміна http_json/http_download: HEAD можна «зрушити», лічильники запитів."""

    def __init__(self, files=FILES, root=LIGHT, head="a" * 40, full_root=FULL):
        self.files, self.root, self.head, self.full_root = files, root, head, full_root
        self.calls = {"commit": 0, "tree": 0, "raw": 0, "zip": 0}
        self.broken: set[str] = set()

    def json(self, url):
        if "/commits/" in url:
            self.calls["commit"] += 1
            return {"sha": self.head}
        self.calls["tree"] += 1
        roots = [self.root, self.full_root] if self.root == LIGHT else [self.root]
        tree = [{"path": r + p, "type": "blob", "sha": git_sha(b if p not in self.broken else b + b"!"), "size": len(b)}
                for r in roots for p, b in self.files.items()]
        return {"tree": tree + [{"path": "README.md", "type": "blob", "sha": "0" * 40}], "truncated": False}

    def download(self, url, dest):
        dest.parent.mkdir(parents=True, exist_ok=True)
        if "codeload" in url:
            self.calls["zip"] += 1
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as z:
                for p, b in self.files.items():
                    z.writestr(f"repo-{self.head}/{self.full_root}{p}", b)
                z.writestr(f"repo-{self.head}/{self.full_root}../evil.txt", b"x")
                z.writestr(f"repo-{self.head}/README.md", b"r")
            data = buf.getvalue()
        else:
            self.calls["raw"] += 1
            from urllib.parse import unquote
            path = unquote(url.split(f"/{self.head}/", 1)[1])
            data = self.files[path[len(self.root):]]
        dest.write_bytes(data)
        return hashlib.sha256(data).hexdigest(), len(data)


@pytest.fixture
def net(tmp_path, monkeypatch):
    monkeypatch.setenv("WC3UA_ROOT", str(tmp_path / "repo"))
    n = Net()
    monkeypatch.setattr(tp, "http_json", n.json)
    monkeypatch.setattr(tp, "http_download", n.download)
    return n


def tgt(tid="classic-1.31"):
    return tp.load_target(tid)


def test_resolve_head_and_ref(net):
    assert tp.resolve_commit() == "a" * 40 and net.calls["commit"] == 1
    assert tp.resolve_commit("b" * 40) == "b" * 40 and net.calls["commit"] == 1      # повний sha — без запиту
    net.head = "zzz"
    with pytest.raises(tp.TextPackError):
        tp.resolve_commit("v1.0")


def test_light_download_verifies_and_records(net, tmp_path):
    up = tp.get_upstream(tgt(), False, log=lambda *_: None)
    man = json.loads((up["files_dir"].parent / "manifest.json").read_text())
    assert up["commit"] == "a" * 40 and man["commit"] == "a" * 40 and len(man["archive_sha256"]) == 64
    assert (up["files_dir"] / "Units/humanunitstrings.txt").read_bytes() == UNITS.encode()
    assert not (up["files_dir"] / "fonts").exists() and not (up["files_dir"] / "classic").exists()   # classic: шрифти свої, LIGHT
    assert man["files"]["Units/commandstrings.txt"]["sha256"] == hashlib.sha256(FILES["Units/commandstrings.txt"]).hexdigest()


def test_cache_hit_then_moved_head_redownloads(net):
    tp.get_upstream(tgt(), False, log=lambda *_: None)
    raw1 = net.calls["raw"]
    tp.get_upstream(tgt(), False, log=lambda *_: None)
    assert net.calls["raw"] == raw1 and net.calls["tree"] == 1           # HEAD той самий → кеш
    net.head = "b" * 40
    up = tp.get_upstream(tgt(), False, log=lambda *_: None)
    assert up["commit"] == "b" * 40 and net.calls["raw"] > raw1 and net.calls["tree"] == 2


def test_ref_pin_ignores_head(net):
    net.head = "c" * 40
    up = tp.get_upstream(tgt(), False, ref="c" * 40, log=lambda *_: None)
    assert up["commit"] == "c" * 40 and net.calls["commit"] == 0


def test_corrupted_cache_is_refetched(net):
    up = tp.get_upstream(tgt(), False, log=lambda *_: None)
    (up["files_dir"] / "Units/commandstrings.txt").write_bytes(b"x")
    n = net.calls["raw"]
    tp.get_upstream(tgt(), False, log=lambda *_: None)
    assert net.calls["raw"] > n


def test_sha_mismatch_aborts_and_leaves_no_cache(net, tmp_path):
    net.broken.add("Units/commandstrings.txt")
    with pytest.raises(tp.TextPackError, match="sha1"):
        tp.get_upstream(tgt(), False, log=lambda *_: None)
    assert not list((tmp_path / "repo/data/local/cache/textpack").glob("a*/light"))


def test_offline_uses_last_cache_but_ref_does_not(net, monkeypatch):
    tp.get_upstream(tgt(), False, log=lambda *_: None)
    monkeypatch.setattr(tp, "http_json", lambda url: (_ for _ in ()).throw(OSError("offline")))
    logs = []
    assert tp.get_upstream(tgt(), False, log=logs.append)["commit"] == "a" * 40 and any("недоступний" in x for x in logs)
    with pytest.raises(tp.TextPackError):
        tp.get_upstream(tgt(), False, ref="v1", log=lambda *_: None)


@pytest.mark.parametrize("files,root,msg", [
    ({"Units/readme.md": b"x"}, LIGHT, "Units"),                        # немає Units/*.txt
    (FILES, "Elsewhere/", "розклад"),                                   # теку LIGHT перейменовано
])
def test_layout_drift_fails_safe(net, files, root, msg):
    net.files, net.root = files, root
    with pytest.raises(tp.TextPackError, match=msg):
        tp.get_upstream(tgt(), False, log=lambda *_: None)


def test_full_variant_zip_extracts_only_wanted_dirs_safely(net):
    up = tp.get_upstream(tgt(), True, log=lambda *_: None)
    fd = up["files_dir"]
    assert (fd / "classic/roc/human01.w3m").exists() and (fd / "movies/captions/a.srt").exists()
    assert not (fd / "webui").exists() and not (fd.parent.parent / "evil.txt").exists() and not (fd / "../evil.txt").resolve().exists()
    assert up["variant"] == "full" and net.calls["zip"] == 1 and not (fd.parent / "archive.zip").exists()


def test_layout_drift_unknown_top_dir_reported(net, tmp_path):
    net.files = {**FILES, "newdir/a.txt": b"x"}
    t = {**tgt(), "full_dirs": ["newdir"]}
    up = tp.get_upstream(t, True, log=lambda *_: None)
    res = tp.build(t, up)
    assert "newdir/a.txt" in res.files                                    # додано в цілі — береться


# ---------------------------------------------------------------- build по цілях
def own_fdf(d: Path):
    d.mkdir(parents=True, exist_ok=True)
    fdf(d / "globalstrings.fdf", {"KEY_OK": "Ok"}, crlf=True)
    return d


def test_build_classic_applies_hotkeys_fdf_fonts(net, tmp_path):
    up = tp.get_upstream(tgt(), False, log=lambda *_: None)
    src = up["files_dir"]
    fdf(src / "UI/framedef/globalstrings.fdf", {"KEY_OK": "Гаразд"})
    fonts = tmp_path / "fonts"
    fonts.mkdir()
    (fonts / "frizqt__.ttf").write_bytes(b"CYR")
    res = tp.build(tgt(), up, fdf_template=own_fdf(tmp_path / "tpl"), fonts_from=fonts, out=tmp_path / "out")
    assert f"({K}A|r)" in res.files["Units/commandstrings.txt"].read_text(encoding="utf-8")
    assert res.stats["hotkeys"]["markers_added"] == 2
    assert res.files["fonts/frizqt__.ttf"].read_bytes() == b"CYR" and res.stats["fonts"] == ["frizqt__.ttf"]
    assert "Гаразд" in res.files["UI/framedef/globalstrings.fdf"].read_text(encoding="utf-8")


def test_build_classic_without_template_skips_not_breaks(net, tmp_path):
    up = tp.get_upstream(tgt(), False, log=lambda *_: None)
    res = tp.build(tgt(), up, out=tmp_path / "out")
    assert not any(r.startswith("UI/framedef") for r in res.files)
    assert any("FDF 1.31" in s for s in res.skipped) and any("шрифти" in s for s in res.skipped)


def test_build_reforged_native_no_hotkeys_upstream_fdf_and_fonts(net, tmp_path):
    t = tgt("reforged")
    up = tp.get_upstream(t, False, log=lambda *_: None)
    fdf(up["files_dir"] / "UI/framedef/globalstrings.fdf", {"A": "b"})
    res = tp.build(t, up, out=tmp_path / "out")
    assert res.files["Units/commandstrings.txt"].read_bytes() == FILES["Units/commandstrings.txt"]
    assert res.files["UI/framedef/globalstrings.fdf"].parent.name == "framedef" and "fonts/frizqt__.ttf" in res.files


def test_build_legacy_excludes_skin_files(net, tmp_path):
    t = tgt("legacy")
    up = tp.get_upstream(t, False, log=lambda *_: None)
    res = tp.build(t, up, out=tmp_path / "out")
    assert "Units/unitskinstrings.txt" not in res.files and not any(r.startswith("doodads/") for r in res.files)
    assert "Units/humanunitstrings.txt" in res.files and any("FDF 1.31" in s for s in res.skipped)


def test_targets_are_complete():
    ids = {t["id"] for t in tp.all_targets()}
    assert ids == {"classic-1.31", "reforged", "legacy"}
    for t in tp.all_targets():
        assert t["status"] in ("supported", "experimental") and t["local_files"] and t["notes"]
    assert tgt("reforged")["game_subdir"] == "_retail_" and tgt("reforged")["hotkey_markers"] is False
    with pytest.raises(tp.TextPackError):
        tp.load_target("nope")


def test_casc_extract_reports_failure(monkeypatch, tmp_path):
    class R:
        returncode, stderr, stdout = 1, "boom", ""
    monkeypatch.setattr(tp.subprocess, "run", lambda *a, **k: R())
    with pytest.raises(tp.TextPackError, match="CASC"):
        tp.casc_extract(tmp_path, "x", tmp_path / "o")


def test_own_source_prefers_explicit_then_language_pack(tmp_path):
    assert tp.own_source(tmp_path, "fonts", tmp_path / "x", tmp_path) == tmp_path / "x"
    pack = tmp_path / "Localizations/Russian/ruru.w3mod/fonts"
    pack.mkdir(parents=True)
    assert tp.own_source(tmp_path, "fonts", None, tmp_path / "w") == pack
