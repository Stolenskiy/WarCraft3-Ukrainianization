"""Обрані в студії дублі (game-files/) → корінь гри, з бекапом, журналом і відкатом.

  make install-voices            # показати план (нічого не змінює)
  make install-voices APPLY=1    # встановити
  make uninstall-voices          # прибрати встановлене нами й повернути оригінали з бекапу

Безпека (див. .claude/skills/game-change/SKILL.md):
  * ціль має реально (realpath) лежати в корені гри, але не в Mods/ чи Data/ — інакше пропуск
    (типово: Units/orc/<юніт> — симлінк на Mods/…; такі юніти поки не встановлюються, див. вивід);
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
from pathlib import Path

ROOT = Path(os.environ.get("WC3UA_ROOT") or Path(__file__).resolve().parent.parent)
GAME = Path(os.environ.get("WC3_GAME_ROOT", "/Applications/Warcraft III Classic"))


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def safe_target(game: Path, rel: str) -> Path | None:
    g = game.resolve()
    real = (game / rel).resolve()
    if not str(real).startswith(str(g) + os.sep) or real.is_relative_to(g / "Mods") or real.is_relative_to(g / "Data"):
        return None
    return game / rel


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--uninstall", action="store_true")
    a = ap.parse_args(argv)
    bdir = GAME / "Backups/ua-voices"
    man_p = bdir / "manifest.json"
    manifest = json.loads(man_p.read_text()) if man_p.exists() else {}
    log = []

    if a.uninstall:
        for rel, info in sorted(manifest.items()):
            t = GAME / rel
            if t.exists() and sha(t) == info["sha256"]:
                t.unlink()
                if info.get("backup"):
                    shutil.copy2(bdir / "originals" / rel, t)
                log.append(f"REMOVED {rel}" + (" (original restored)" if info.get("backup") else ""))
            else:
                log.append(f"SKIP {rel}: змінений не нами — не чіпаю")
        manifest = {}
    else:
        src_root = ROOT / "game-files"
        files = sorted(p for p in src_root.rglob("*.wav"))
        if not files:
            print("game-files/ порожня — оберіть дублі в студії (✓ Обрати)")
            return 1
        for src in files:
            rel = src.relative_to(src_root).as_posix()
            t = safe_target(GAME, rel)
            if t is None:
                print(f"ПРОПУСК {rel}: тека в грі — симлінк у Mods/ (потрібна процедура game-change)")
                continue
            if t.exists() and rel in manifest and sha(t) == sha(src):
                print(f"вже є   {rel}")
                continue
            print(f"{'СТАВЛЮ' if a.apply else 'буде'}  {rel}")
            if not a.apply:
                continue
            backup = False
            if t.exists() and rel not in manifest:          # чужий файл → бекап оригіналу
                (bdir / "originals" / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(t, bdir / "originals" / rel)
                backup = True
            t.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, t)
            manifest[rel] = {"sha256": sha(t), "backup": backup or manifest.get(rel, {}).get("backup", False)}
            log.append(f"INSTALLED {rel} sha256={manifest[rel]['sha256']}" + (" (original backed up)" if backup else ""))
        if not a.apply:
            print("\nЦе план. Встановити: make install-voices APPLY=1")
            return 0

    bdir.mkdir(parents=True, exist_ok=True)
    man_p.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    with open(bdir / "CHANGE-LOG.txt", "a", encoding="utf-8") as f:
        f.write(f"\n== {dt.datetime.now().isoformat(timespec='seconds')} "
                f"{'uninstall' if a.uninstall else 'install'} (tools/install_voices.py)\n")
        f.write("ROLLBACK: make uninstall-voices\n" + "".join(x + "\n" for x in log))
    print("\n".join(log) or "нічого не змінено")
    return 0


if __name__ == "__main__":
    sys.exit(main())
