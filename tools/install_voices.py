"""Обрані в студії дублі (game-files/) → корінь гри, з бекапом, журналом і відкатом.

  make install-voices            # показати план (нічого не змінює)
  make install-voices APPLY=1    # встановити
  make uninstall-voices          # прибрати встановлене нами й повернути оригінали з бекапу
Те саме робить кнопка «Встановити в гру» в студії (plan/apply/uninstall нижче; без shell).

Безпека (див. .claude/skills/game-change/SKILL.md):
  * писати можна лише в реальну (realpath) теку всередині кореня гри, не в Mods/ чи Data/;
  * теку юніта, що є СИМЛІНКОМ (типово Units/orc/<юніт> → Mods/Reforged Models/...), «матеріалізуємо»:
    симлінк замінюється реальною текою з симлінками (абсолютні цілі, як у Units/orc/peon) на кожен
    елемент оригінальної цілі; наш wav — звичайний файл поруч. Оригінальний шлях і readlink
    записуються в manifest.json; при відкаті, якщо в теці лишились лише наші симлінки,
    її видалено, а симлінк повернено з тим самим рядком readlink. У Mods/ нічого не пишемо;
  * чужий файл, що перезаписується, спершу копіюється в Backups/ua-voices/originals/;
  * усе встановлене записується в Backups/ua-voices/manifest.json і CHANGE-LOG.txt.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))   # `python -I` не додає теку скрипта
import gameconf  # noqa: E402

import voices  # noqa: E402

ROOT = Path(os.environ.get("WC3UA_ROOT") or Path(__file__).resolve().parent.parent)
GAME = gameconf.get_game_root()
LOCK = threading.Lock()


class InstallError(Exception):
    pass


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def safe_target(game: Path, rel: str) -> Path | None:
    g = game.resolve()
    real = (game / rel).resolve()
    if not str(real).startswith(str(g) + os.sep) or real.is_relative_to(g / "Mods") or real.is_relative_to(g / "Data"):
        return None
    return game / rel


# ---------------------------------------------------------------- маніфест
def _load(game: Path) -> dict:
    p = game / "Backups/ua-voices/manifest.json"
    m = json.loads(p.read_text()) if p.exists() else {}
    if "files" not in m and "materialized" not in m:      # старий формат: {rel: {sha256, backup}}
        m = {"files": m}
    m.setdefault("files", {})
    m.setdefault("materialized", {})
    return m


def _save(game: Path, m: dict) -> None:
    bdir = game / "Backups/ua-voices"
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / "manifest.json").write_text(json.dumps(m, indent=2, ensure_ascii=False))


def _sources(root: Path, sources: dict[str, Path] | None = None) -> dict[str, Path]:
    """rel → файл-джерело (wav або flac). Без явного sources — за збереженим вибором голосів (voices.resolve;
    типово лише локальна game-files/)."""
    if sources is None:
        sources = voices.build_sources(root)
    if not sources:
        raise InstallError("немає що встановлювати — оберіть дублі в студії (✓ Обрати) або голоси спільноти")
    return dict(sorted(sources.items()))


def _wav(src: Path, root: Path) -> Path:
    """FLAC → wav у кеші (за sha); wav як є."""
    try:
        return voices.stage(src, root) if src.suffix == ".flac" else src
    except voices.VoiceError as ex:
        raise InstallError(str(ex)) from ex


# ---------------------------------------------------------------- класифікація цілі
def classify(game: Path, rel: str, mat: dict | None = None) -> tuple[str, str, str]:
    """('ok'|'materialize'|'skip', rel теки-симлінка або '', причина). mat — матеріалізовані нами теки (з маніфесту)."""
    parts = Path(rel).parts
    cur = game
    for i, part in enumerate(parts[:-1]):
        cur = cur / part
        if not cur.is_symlink():
            continue
        lrel = "/".join(parts[: i + 1])
        if i != len(parts) - 2:
            return "skip", "", f"симлінк {lrel} не є текою юніта (вкладені шляхи не підтримуються)"
        if not cur.is_dir():
            return "skip", "", f"симлінк {lrel} веде не в теку"
        if safe_target(game, "/".join(parts[:i])) is None and i > 0:
            return "skip", "", f"батьківська тека {'/'.join(parts[:i])} — не безпечна"
        return "materialize", lrel, ""
    parent = Path(rel).parent.as_posix()
    if parent in (mat or {}) and (game / rel).is_symlink() and safe_target(game, parent) is not None:
        return "ok", "", ""                      # наш відтворений симлінк-елемент: замінюємо, а не пишемо крізь нього
    if safe_target(game, rel) is None:
        return "skip", "", "ціль веде в Mods/ або Data/ чи поза грою"
    return "ok", "", ""


def _link_info(game: Path, lrel: str) -> tuple[str, str, list[str]]:
    """(рядок readlink, абсолютна ціль, імена елементів цілі)."""
    link = game / lrel
    raw = os.readlink(link)
    absdir = os.path.normpath(os.path.join(os.path.realpath(link.parent), raw))
    return raw, absdir, sorted(os.listdir(link))


# ---------------------------------------------------------------- план
def plan(game: Path | None = None, root: Path | None = None, sources: dict[str, Path] | None = None) -> dict:
    """Сухий прогін. files: [{rel, status: new|update|same, materialize: теку-симлінк або '', author, wanted, fallback, alts}],
    materialize: [{rel, link, entries}], skipped: [{rel, reason}]."""
    game = Path(game or GAME)
    if not game.is_dir():
        raise InstallError(f"тека гри не знайдена: {game}")
    root = root or ROOT
    man = _load(game)
    out = {"game": str(game), "files": [], "materialize": [], "skipped": [], "same": 0}
    mat: dict[str, dict] = {}
    picks = voices.resolve(root) if sources is None else {}
    for rel, src in _sources(root, sources if sources is not None else {r: p.path for r, p in picks.items()}).items():
        kind, lrel, why = classify(game, rel, man["materialized"])
        if kind == "skip":
            out["skipped"].append({"rel": rel, "reason": why})
            continue
        t = game / rel
        if kind == "materialize":
            if lrel not in mat:
                raw, absdir, names = _link_info(game, lrel)
                mat[lrel] = {"rel": lrel, "link": raw, "entries": len(names)}
            status = "update" if os.path.lexists(os.path.join(os.path.realpath(game / lrel), t.name)) else "new"
        elif t.exists() and not t.is_symlink() and sha(t) == sha(_wav(src, root)):
            status = "same"
        else:
            status = "update" if t.exists() else "new"
        out["same"] += status == "same"
        pk = picks.get(rel)
        out["files"].append({"rel": rel, "status": status, "materialize": lrel, "author": pk.author if pk else voices.LOCAL,
                             "wanted": pk.wanted if pk else "", "fallback": bool(pk and pk.fallback),
                             "alts": pk.alts if pk else [voices.LOCAL]})
    out["materialize"] = list(mat.values())
    return out


def uninstall_plan(game: Path | None = None) -> dict:
    """Що можна прибрати: файли з маніфесту. status: present|changed|missing."""
    game = Path(game or GAME)
    if not game.is_dir():
        raise InstallError(f"тека гри не знайдена: {game}")
    man = _load(game)
    files = []
    for rel, info in sorted(man["files"].items()):
        t = game / rel
        st = ("present" if sha(t) == info["sha256"] else "changed") if t.is_file() and not t.is_symlink() else "missing"
        files.append({"rel": rel, "status": st, "materialize": str(Path(rel).parent) if str(Path(rel).parent) in man["materialized"] else ""})
    return {"game": str(game), "files": files, "materialize": [{"rel": k, "link": v["link_target"]} for k, v in man["materialized"].items()]}


# ---------------------------------------------------------------- встановлення
def _materialize(game: Path, lrel: str, man: dict, log: list[str]) -> None:
    link = game / lrel
    raw, absdir, names = _link_info(game, lrel)
    tmp = link.with_name(link.name + ".ua-tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    entries = {n: f"{absdir}/{n}" for n in names}
    tmp.mkdir()
    try:
        for n, tgt in entries.items():
            os.symlink(tgt, tmp / n)
        os.unlink(link)
        try:
            os.rename(tmp, link)
        except OSError:
            os.symlink(raw, link)                # відкат: повернути оригінальний симлінк
            raise
    except OSError:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    man["materialized"][lrel] = {"link_target": raw, "entries": entries}
    log.append(f"MATERIALIZED {lrel} (was symlink -> {raw}; {len(entries)} symlinks recreated)")


def apply(game: Path | None = None, root: Path | None = None, files: list[str] | None = None,
          sources: dict[str, Path] | None = None) -> dict:
    """files — обрані game_rel (None = усе з плану); невідомий шлях → InstallError."""
    game = Path(game or GAME)
    with LOCK:
        root = root or ROOT
        pl = plan(game, root, sources)    # перевірки + _sources (None → за збереженим вибором голосів)
        valid = {f["rel"] for f in pl["files"]}
        chosen = valid if files is None else set(files)
        if chosen - valid:
            raise InstallError("невідомі шляхи: " + ", ".join(sorted(chosen - valid)[:5]))
        pl["materialize"] = [m for m in pl["materialize"] if any(f["rel"] in chosen and f["materialize"] == m["rel"] for f in pl["files"])]
        pl["same"] = sum(f["status"] == "same" and f["rel"] in chosen for f in pl["files"])
        bdir = game / "Backups/ua-voices"
        man = _load(game)
        log: list[str] = []
        installed = skipped = 0
        for rel, src in _sources(root, sources).items():     # під LOCK — вибір не змінюється між планом і копіюванням
            if rel not in chosen:
                continue
            kind, lrel, _ = classify(game, rel, man["materialized"])
            if kind == "skip":
                skipped += 1
                continue
            t = game / rel
            if kind == "materialize":
                _materialize(game, lrel, man, log)
                _save(game, man)                  # маніфест одразу: матеріалізація має відкат
                if safe_target(game, rel) is None or not t.parent.resolve().is_relative_to(game.resolve() / lrel):
                    raise InstallError(f"{rel}: після матеріалізації ціль небезпечна — зупинено")
            src = _wav(src, root)
            if t.exists() and rel in man["files"] and sha(t) == sha(src):
                continue
            backup = False
            if t.is_symlink():                      # наш власний відтворений симлінк — просто замінюємо
                t.unlink()
            elif t.exists() and rel not in man["files"]:   # чужий файл → бекап оригіналу
                (bdir / "originals" / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(t, bdir / "originals" / rel)
                backup = True
            t.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, t)
            man["files"][rel] = {"sha256": sha(t), "backup": backup or man["files"].get(rel, {}).get("backup", False)}
            installed += 1
            log.append(f"INSTALLED {rel} sha256={man['files'][rel]['sha256']}" + (" (original backed up)" if backup else ""))
        _save(game, man)
        _changelog(game, "install", log, man)
        return {"installed": installed, "unchanged": pl["same"], "materialized": [m["rel"] for m in pl["materialize"]],
                "skipped": [] if files is not None else pl["skipped"], "log": log}


# ---------------------------------------------------------------- відкат
def _unmaterialize(game: Path, lrel: str, info: dict, log: list[str]) -> bool:
    d = game / lrel
    if d.is_symlink() or not d.is_dir():
        log.append(f"SKIP {lrel}: не матеріалізована тека — не чіпаю")
        return False
    entries = info["entries"]
    for n, tgt in entries.items():                 # елементи, замінені нашими файлами (вже прибрані)
        if not os.path.lexists(d / n):
            os.symlink(tgt, d / n)
    names = set(os.listdir(d))
    if names != set(entries) or any(not (d / n).is_symlink() or os.readlink(d / n) != entries[n] for n in names):
        log.append(f"SKIP {lrel}: у теці є сторонні файли — лишаю матеріалізованою")
        return False
    for n in names:
        os.unlink(d / n)
    d.rmdir()
    os.symlink(info["link_target"], d)
    log.append(f"RESTORED SYMLINK {lrel} -> {info['link_target']}")
    return True


def uninstall(game: Path | None = None, files: list[str] | None = None) -> dict:
    """files — що прибрати (None = усе з маніфесту); невідомий шлях → InstallError.
    Симлінк теки повертається лише коли в ній не лишилось наших файлів."""
    game = Path(game or GAME)
    with LOCK:
        bdir = game / "Backups/ua-voices"
        man = _load(game)
        chosen = set(man["files"]) if files is None else set(files)
        if chosen - set(man["files"]):
            raise InstallError("невідомі шляхи: " + ", ".join(sorted(chosen - set(man["files"]))[:5]))
        log: list[str] = []
        for rel in sorted(chosen):
            info, t = man["files"][rel], game / rel
            if t.exists() and not t.is_symlink() and sha(t) == info["sha256"]:
                t.unlink()
                if info.get("backup"):
                    shutil.copy2(bdir / "originals" / rel, t)
                log.append(f"REMOVED {rel}" + (" (original restored)" if info.get("backup") else ""))
            else:
                log.append(f"SKIP {rel}: змінений не нами — не чіпаю")
        rest = {r: i for r, i in man["files"].items() if r not in chosen}
        busy = {str(Path(r).parent) for r in rest}
        left = {}
        for lrel, i in sorted(man["materialized"].items(), reverse=True):
            if lrel in busy or not _unmaterialize(game, lrel, i, log):
                left[lrel] = i
        _save(game, {"files": rest, "materialized": left})
        _changelog(game, "uninstall", log, {"materialized": {}})
        return {"removed": sum(x.startswith("REMOVED") for x in log), "restored_links": [
            x.split()[2] for x in log if x.startswith("RESTORED SYMLINK")], "log": log}


def _changelog(game: Path, what: str, log: list[str], man: dict) -> None:
    bdir = game / "Backups/ua-voices"
    bdir.mkdir(parents=True, exist_ok=True)
    with open(bdir / "CHANGE-LOG.txt", "a", encoding="utf-8") as f:
        f.write(f"\n== {dt.datetime.now().isoformat(timespec='seconds')} {what} (tools/install_voices.py)\n")
        f.write("ROLLBACK: make uninstall-voices\n")
        if what == "install":
            for lrel, i in man["materialized"].items():
                f.write(f"ROLLBACK (вручну, {lrel}): rm -r '{game / lrel}' && ln -s '{i['link_target']}' '{game / lrel}'\n")
        f.write("".join(x + "\n" for x in log))


# ---------------------------------------------------------------- CLI
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--uninstall", action="store_true")
    a = ap.parse_args(argv)
    try:
        if a.uninstall:
            print("\n".join(uninstall(GAME)["log"]) or "нічого не змінено")
        elif a.apply:
            print("\n".join(apply(GAME, ROOT)["log"]) or "нічого не змінено")
        else:
            pl = plan(GAME, ROOT)
            for m in pl["materialize"]:
                print(f"МАТЕРІАЛІЗУЮ {m['rel']} (симлінк → {m['link']}, {m['entries']} елементів)")
            for c in pl["files"]:
                if c["status"] != "same":
                    print(f"буде  {c['rel']}  ← {c['author']}" + (" (запасний: обраного автора немає)" if c["fallback"] else "")
                          + (" (замінить файл, оригінал у бекап)" if c["status"] == "update" else ""))
            for s in pl["skipped"]:
                print(f"ПРОПУСК {s['rel']}: {s['reason']}")
            print(f"вже є: {pl['same']}\n\nЦе план. Встановити: make install-voices APPLY=1")
    except InstallError as e:
        print(e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
