"""Єдиний інсталятор: текст + голос для цілі (classic-1.31 | reforged | legacy). Сухий прогін за замовчуванням.

  python tools/run.py install --target classic-1.31 --parts text,voice [--full] [--ref SHA] [--apply]
  python tools/run.py uninstall --target classic-1.31 --parts text,voice
Текст: tools/textpack.py будує дерево (upstream з gitignored кешу + наші перетворення), тут — безпечний запис:
бекап чужого в <корінь>/Backups/ua-text/originals/, manifest.json, CHANGE-LOG.txt (з комітом upstream і sha256),
відкат однією командою; збій посеред запису → автоматичний відкат цього запуску (часткового встановлення не лишаємо).
Голос: tools/install_voices.py (той самий бекап, матеріалізація симлінків) із коренем цілі.
Корінь цілі = <гра з tools/gameconf.py>/<game_subdir> (Reforged: _retail_). Mods/ і Data/ не чіпаємо, нічого не видаляємо.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))   # `python -I` не додає теку скрипта
import gameconf  # noqa: E402
import install_voices as iv  # noqa: E402
import textpack  # noqa: E402

PARTS = ("text", "voice")
NS = "Backups/ua-text"


class PackError(Exception):
    pass


def target_root(target: dict, game: Path) -> Path:
    root = Path(game) / target.get("game_subdir", "")
    if not root.is_dir():
        hint = " (для Reforged це тека _retail_ у теці гри)" if target.get("game_subdir") else ""
        raise PackError(f"тека цілі не знайдена: {root}{hint}")
    return root


def _load(root: Path) -> dict:
    p = root / NS / "manifest.json"
    m = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}
    m.setdefault("files", {})
    m.setdefault("materialized", {})
    return m


def _save(root: Path, m: dict) -> None:
    (root / NS).mkdir(parents=True, exist_ok=True)
    (root / NS / "manifest.json").write_text(json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8")


def _case_fix(root: Path, rel: str) -> str:
    """Якщо в цілі вже є файл із тим самим іменем в іншому регістрі (CASC-імена: OrcUnitStrings.txt) — зберегти його регістр."""
    d, name = root / Path(rel).parent, Path(rel).name
    if d.is_dir():
        names = os.listdir(d)                    # не exists(): на macOS/Windows регістр не розрізняється
        if name not in names:
            for n in names:
                if n.lower() == name.lower():
                    return (Path(rel).parent / n).as_posix()
    return rel


def plan_text(root: Path, tree: dict[str, Path]) -> dict:
    man = _load(root)
    out = {"files": [], "skipped": [], "materialize": [], "same": 0}
    seen = set()
    for rel0, src in sorted(tree.items()):
        rel = _case_fix(root, rel0)
        kind, lrel, why = iv.classify(root, rel, man["materialized"])
        if kind == "skip":
            out["skipped"].append({"rel": rel, "reason": why})
            continue
        if kind == "materialize" and lrel not in seen:
            seen.add(lrel)
            raw, _, names = iv._link_info(root, lrel)
            out["materialize"].append({"rel": lrel, "link": raw, "entries": len(names)})
        t = root / rel
        if kind == "materialize":
            status = "new"
        elif t.is_file() and not t.is_symlink() and iv.sha(t) == iv.sha(src):
            status = "same"
        else:
            status = "update" if os.path.lexists(t) else "new"
        out["same"] += status == "same"
        out["files"].append({"rel": rel, "src": src, "status": status, "materialize": lrel})
    return out


def _changelog(root: Path, what: str, log: list[str], head: list[str]) -> None:
    (root / NS).mkdir(parents=True, exist_ok=True)
    with open(root / NS / "CHANGE-LOG.txt", "a", encoding="utf-8") as f:
        f.write(f"\n== {dt.datetime.now().isoformat(timespec='seconds')} {what} (tools/install_pack.py)\n")
        f.write("".join(h + "\n" for h in head))
        f.write("".join(x + "\n" for x in log))


def apply_text(root: Path, tree: dict[str, Path], meta: dict) -> dict:
    """Все або нічого: помилка посеред запису відкочує зроблене цим запуском."""
    pl = plan_text(root, tree)
    man = _load(root)
    old = json.loads(json.dumps(man))
    bdir = root / NS
    log: list[str] = []
    undo: list = []
    installed = 0
    try:
        for m in pl["materialize"]:
            iv._materialize(root, m["rel"], man, log)
        for f in pl["files"]:
            rel, src, t = f["rel"], f["src"], root / f["rel"]
            if f["status"] == "same" and rel in man["files"]:
                continue
            backup = False
            if t.is_symlink():
                t.unlink()
            elif t.exists() and rel not in man["files"]:
                (bdir / "originals" / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(t, bdir / "originals" / rel)
                backup = True
            elif t.exists():
                (bdir / "prev" / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(t, bdir / "prev" / rel)
                undo.append((t, bdir / "prev" / rel))
            t.parent.mkdir(parents=True, exist_ok=True)
            if not t.exists():
                undo.append((t, None))
            shutil.copy2(src, t)
            man["files"][rel] = {"sha256": iv.sha(t), "backup": backup or man["files"].get(rel, {}).get("backup", False)}
            installed += 1
            log.append(f"INSTALLED {rel} sha256={man['files'][rel]['sha256']}" + (" (original backed up)" if backup else ""))
    except (OSError, iv.InstallError) as ex:
        for t, prev in reversed(undo):
            if prev is not None:
                shutil.copy2(prev, t)
            elif t.exists():
                t.unlink()
        for rel, i in man["files"].items():       # оригінали, які встигли забекапити, повертаємо
            if rel not in old["files"] and i.get("backup") and (bdir / "originals" / rel).is_file():
                shutil.copy2(bdir / "originals" / rel, root / rel)
        for lrel, i in man["materialized"].items():
            if lrel not in old["materialized"]:
                iv._unmaterialize(root, lrel, i, [])
        raise PackError(f"запис перервано ({ex}); зроблене цим запуском відкочено, гра як була") from ex
    man["source"] = meta
    _save(root, man)
    head = [f"SOURCE upstream {meta.get('repo', textpack.REPO)} commit={meta.get('commit')} variant={meta.get('variant')} "
            f"archive_sha256={meta.get('archive_sha256')} target={meta.get('target')}",
            f"ROLLBACK: python tools/run.py uninstall --target {meta.get('target')} --parts text"]
    _changelog(root, "install text", log, head)
    return {"installed": installed, "unchanged": pl["same"], "skipped": pl["skipped"], "log": log}


def uninstall_text(root: Path) -> dict:
    bdir = root / NS
    man = _load(root)
    log: list[str] = []
    for rel, info in sorted(man["files"].items()):
        t = root / rel
        if t.is_file() and not t.is_symlink() and iv.sha(t) == info["sha256"]:
            t.unlink()
            if info.get("backup") and (bdir / "originals" / rel).is_file():
                shutil.copy2(bdir / "originals" / rel, t)
            log.append(f"REMOVED {rel}" + (" (original restored)" if info.get("backup") else ""))
        else:
            log.append(f"SKIP {rel}: змінений не нами або вже відсутній — не чіпаю")
    left = {}
    for lrel, i in sorted(man["materialized"].items(), reverse=True):
        if not iv._unmaterialize(root, lrel, i, log):
            left[lrel] = i
    _save(root, {"files": {}, "materialized": left})
    _changelog(root, "uninstall text", log, [])
    return {"removed": sum(x.startswith("REMOVED") for x in log), "log": log}


# ---------------------------------------------------------------- оркестрація
def prepare(target_id: str, full: bool = False, ref: str | None = None, game: Path | None = None,
            fdf_template: Path | None = None, fonts_from: Path | None = None, log=print):
    target = textpack.load_target(target_id)
    game = Path(game or gameconf.get_game_root())
    root = target_root(target, game)
    up = textpack.get_upstream(target, full, ref, log)
    res = textpack.build(target, up, game=game, fdf_template=fdf_template, fonts_from=fonts_from)
    return target, game, root, res


def run(target_id: str, parts: list[str], *, apply: bool = False, full: bool = False, ref: str | None = None,
        game: Path | None = None, fdf_template: Path | None = None, fonts_from: Path | None = None, out=print) -> int:
    bad = [p for p in parts if p not in PARTS]
    if bad:
        out(f"невідома частина: {bad}; є: {', '.join(PARTS)}")
        return 2
    try:
        target = textpack.load_target(target_id)
        game = Path(game or gameconf.get_game_root())
        root = target_root(target, game)
        out(f"ціль: {target['title']} [{target['status'].upper()}]\nкорінь: {root}\n")
        meta = {}
        if "text" in parts:
            _, _, _, res = prepare(target_id, full, ref, game, fdf_template, fonts_from, out)
            meta = {**res.source, "repo": textpack.REPO, "target": target_id}
            pl = plan_text(root, res.files)
            hk = res.stats.get("hotkeys", {})
            new = sum(f["status"] == "new" for f in pl["files"])
            upd = sum(f["status"] == "update" for f in pl["files"])
            out(f"ТЕКСТ: коміт upstream {meta['commit'][:10]} ({meta['variant']}), sha256 {meta['archive_sha256'][:16]}…\n"
                f"  нових {new}, змінюється {upd}, без змін {pl['same']}, пропущено {len(pl['skipped'])}")
            if hk:
                out(f"  гарячі клавіші: маркерів додано {hk.get('markers_added', 0)} у {hk.get('tips_changed', 0)} підказках "
                    f"({hk.get('sections_changed', 0)} секцій; без |c було {hk.get('sections_without_markup', 0)} з "
                    f"{hk.get('sections_with_hotkey', 0)}); пропущено вже з розміткою {hk.get('skipped_already', 0)}, "
                    f"неприйнятна клавіша {hk.get('skipped_badkey', 0)}")
            rp = res.stats.get("repack")
            if rp:
                out(f"  патч балансу репаку: додано ключів {rp['keys']}, секцій {rp['sections']}, характеристик в описах "
                    f"{rp['stats']} (англійською лишилось {rp['english']})")
            for name, r in res.stats.get("fdf", {}).items():
                out(f"  FDF 1.31 {name}: id {r['ids']}, перекладено {r['translated']}, лишились англійськими: "
                    f"немає в upstream {len(r['missing_in_upstream'])}, інші %-специфікатори {len(r['format_mismatch'])}")
            if "fonts" in res.stats:
                out(f"  шрифти з вашої гри: {', '.join(res.stats['fonts']) or 'немає'}")
            for s in res.skipped + [f"{x['rel']}: {x['reason']}" for x in pl["skipped"]]:
                out(f"  ПРОПУСК {s}")
            if apply:
                r = apply_text(root, res.files, meta)
                out(f"  встановлено {r['installed']}, без змін {r['unchanged']}. Відкат: python tools/run.py uninstall "
                    f"--target {target_id} --parts text")
        if "voice" in parts:
            if target.get("voice") == "experimental":
                out("ГОЛОС: ЕКСПЕРИМЕНТАЛЬНО для цієї цілі (не перевірено на справжній грі)")
            try:
                vp = iv.plan(root)
                out(f"ГОЛОС: файлів {len(vp['files'])} (без змін {vp['same']}), симлінків до матеріалізації "
                    f"{len(vp['materialize'])}, пропущено {len(vp['skipped'])}")
                if apply:
                    r = iv.apply(root)
                    out(f"  встановлено {r['installed']}, без змін {r['unchanged']}")
            except iv.InstallError as ex:
                out(f"ГОЛОС: пропущено — {ex}")
        if not apply:
            out("\nЦе план, у гру нічого не записано. Додайте --apply (лише за вашим рішенням).")
        return 0
    except (PackError, textpack.TextPackError, iv.InstallError) as ex:
        out(f"ПОМИЛКА: {ex}")
        return 1


def run_uninstall(target_id: str, parts: list[str], game: Path | None = None, out=print) -> int:
    try:
        target = textpack.load_target(target_id)
        root = target_root(target, Path(game or gameconf.get_game_root()))
        if "text" in parts:
            out(f"текст: прибрано {uninstall_text(root)['removed']} файлів")
        if "voice" in parts:
            out(f"голос: прибрано {iv.uninstall(root)['removed']} файлів")
        return 0
    except (PackError, textpack.TextPackError, iv.InstallError) as ex:
        out(f"ПОМИЛКА: {ex}")
        return 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("action", choices=("install", "uninstall"))
    ap.add_argument("--target", default="classic-1.31", choices=sorted(t["id"] for t in textpack.all_targets()))
    ap.add_argument("--parts", default="text,voice")
    ap.add_argument("--full", action="store_true", help="з кампаніями (~1 ГБ)")
    ap.add_argument("--ref", help="зафіксувати коміт/тег upstream (типово — найновіший main)")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--fdf-template", type=Path)
    ap.add_argument("--fonts-from", type=Path)
    a = ap.parse_args(argv)
    parts = [p.strip() for p in a.parts.split(",") if p.strip()]
    if a.action == "uninstall":
        return run_uninstall(a.target, parts)
    return run(a.target, parts, apply=a.apply, full=a.full, ref=a.ref, fdf_template=a.fdf_template, fonts_from=a.fonts_from)


if __name__ == "__main__":
    sys.exit(main())
