#!/usr/bin/env python3
"""Розділяє транскрипти: тексти оригіналів Blizzard — локально, у git — лише тривалості (ADR 0005, варіант 3).

  data/transcripts-*.json        відстежується: {wav: {"duration": сек}}
  data/local/transcripts-*.json  gitignored:    {wav: {"text": ..., "duration": ...}}

Ідемпотентно й без втрат: якщо локальний файл уже є — його записи лишаються, з джерела додається лише відсутнє.
Запуск: `make transcripts-local`. Перед злиттям гілки в стару копію (де в git ще є тексти) —
`--local-only` (лише копіює тексти в data/local/, відстежувані файли не чіпає).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _dump(p: Path, data: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def merge_local(src: dict, local: dict) -> dict:
    """Локальні записи мають пріоритет; з джерела додається лише відсутнє (текст не втрачається ніколи)."""
    out = {k: dict(v) for k, v in local.items()}
    for wav, info in src.items():
        cur = out.setdefault(wav, {})
        for k in ("text", "duration"):
            if k in info and k not in cur:
                cur[k] = info[k]
    return dict(sorted(out.items()))


def split(root: Path = ROOT, strip: bool = True) -> dict:
    """Повертає {"files": n, "texts": n, "stripped": n}."""
    data_dir, local_dir = root / "data", root / "data/local"
    files = texts = stripped = 0
    for f in sorted(data_dir.glob("transcripts-*.json")):
        src = _load(f)
        if not any("text" in v for v in src.values()):
            continue
        files += 1
        merged = merge_local(src, _load(local_dir / f.name))
        _dump(local_dir / f.name, merged)
        texts += sum(1 for v in merged.values() if v.get("text"))
        if strip:
            _dump(f, {w: {"duration": v["duration"]} for w, v in src.items() if "duration" in v})
            stripped += 1
    return {"files": files, "texts": texts, "stripped": stripped}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--local-only", action="store_true", help="лише скопіювати тексти в data/local/, git-файли не чіпати")
    ap.add_argument("--root", type=Path, default=ROOT)
    a = ap.parse_args(argv)
    r = split(a.root, strip=not a.local_only)
    have = len(list((a.root / "data/local").glob("transcripts-*.json")))
    print(f"розділено файлів: {r['files']}, текстів збережено локально: {r['texts']}, "
          f"очищено відстежуваних: {r['stripped']}; локальних файлів усього: {have}")
    if not have:
        print("Локальних текстів немає: `make refs` (RU-пакет) і `make transcribe`.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
