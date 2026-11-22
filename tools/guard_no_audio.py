#!/usr/bin/env python3
"""Падає, якщо в git (відстежувані або проіндексовані файли) є аудіо, ресурси гри чи секрети.

Ловить і `git add -f` через .gitignore. Дозволено лише пакети голосів спільноти:
voices/LICENSE.md та voices/<автор>/{voice.json, manifest.json, LICENSE.md, units/**.flac}
(їхній вміст окремо перевіряє tools/check_voices.py).
Запуск: `make guard` (входить у `make verify`), .githooks/pre-commit, CI.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

EXTS = ("wav mp3 flac ogg opus m4a aac aif aiff webm w3x w3m mpq blp mdx pem key p12 pfx").split()
BAD = re.compile(
    r"\.(" + "|".join(EXTS) + r")$"
    r"|(^|/)(reference[^/]*|audio[^/]*|models|game-files|backups)/"
    r"|^data/(studio|local)/"
    r"|(^|/)\.env",
    re.I,
)
ALLOW = re.compile(
    r"^voices/LICENSE\.md$"
    r"|^voices/[^/]+/(voice\.json|manifest\.json|LICENSE\.md)$"
    r"|^voices/[^/]+/units/.+\.flac$"
    r"|(^|/)\.env\.(example|sample)$"
)


def violations(files) -> list[str]:
    return sorted(f for f in set(files) if BAD.search(f) and not ALLOW.search(f))


def git_files(root: Path) -> list[str]:
    def run(*a):
        out = subprocess.run(["git", *a], cwd=root, capture_output=True, check=True).stdout
        return [p.decode("utf-8", "surrogateescape") for p in out.split(b"\0") if p]
    return run("ls-files", "-z") + run("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z")


def text_violations(root: Path, files) -> list[str]:
    """data/transcripts-*.json у git — лише тривалості: поле "text" = оригінальні тексти Blizzard (ADR 0005)."""
    bad = []
    for f in sorted(set(files)):
        if not re.fullmatch(r"data/transcripts-[^/]+\.json", f):
            continue
        r = subprocess.run(["git", "show", f":{f}"], cwd=root, capture_output=True)
        raw = r.stdout if r.returncode == 0 else (root / f).read_bytes() if (root / f).exists() else b""
        try:
            data = json.loads(raw)
        except ValueError:
            continue
        if isinstance(data, dict) and any(isinstance(v, dict) and "text" in v for v in data.values()):
            bad.append(f)
    return bad


def main(root: Path | None = None) -> int:
    root = Path(root or Path(__file__).resolve().parent.parent)
    files = git_files(root)
    bad = violations(files) + text_violations(root, files)
    if bad:
        print("ЗАБОРОНЕНО комітити (аудіо, ресурси гри, секрети, data/local/, оригінальні тексти в data/transcripts-*.json):", *bad, sep="\n  ", file=sys.stderr)
        print("Дозволені лише пакети голосів: voices/<автор>/{voice.json,manifest.json,LICENSE.md,units/**.flac}.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else None))
