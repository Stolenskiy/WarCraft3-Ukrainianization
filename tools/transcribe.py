#!/usr/bin/env python3
"""Transcribe Russian reference voice files with mlx-whisper into data/local/ (gitignored, ADR 0005).

Usage:
    .venv/bin/python -I tools/transcribe.py --all            # every reference/units/<race>/<unit> without a local file
    .venv/bin/python -I tools/transcribe.py <input_dir> [out_json]   # default out: data/local/transcripts-<race>-<unit>.json
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCAL = ROOT / "data/local"


def default_out(src: Path) -> Path:
    return LOCAL / f"transcripts-{src.parent.name}-{src.name}.json"


def transcribe_dir(src: Path, out: Path) -> None:
    from mlx_whisper import transcribe

    if not out.resolve().is_relative_to(LOCAL.resolve()):
        sys.exit(f"тексти оригіналів пишемо лише в {LOCAL} (ADR 0005), не в {out}")
    result = {}
    wavs = sorted(src.rglob("*.wav"))
    for i, wav in enumerate(wavs):
        r = transcribe(
            str(wav),
            path_or_hf_repo="mlx-community/whisper-large-v3-turbo",
            language="ru",
        )
        result[str(wav.relative_to(src))] = {
            "text": r["text"].strip(),
            "duration": round(
                r.get("segments", [{}])[-1].get("end", 0.0) if r.get("segments") else 0.0,
                2,
            ),
        }
        if (i + 1) % 20 == 0:
            print(f"{i + 1}/{len(wavs)}", flush=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"wrote {len(result)} entries to {out}")


def main() -> None:
    args = sys.argv[1:]
    if args == ["--all"]:
        dirs = sorted(d for d in (ROOT / "reference/units").glob("*/*") if d.is_dir())
        if not dirs:
            sys.exit("немає reference/units/ — спершу `make refs` (RU-пакет)")
        for d in dirs:
            if not default_out(d).exists() and not (LOCAL / f"transcripts-{d.name}.json").exists():
                transcribe_dir(d, default_out(d))
        return
    if not args:
        sys.exit(__doc__)
    src = Path(args[0])
    transcribe_dir(src, Path(args[1]) if len(args) > 1 else default_out(src.resolve()))


if __name__ == "__main__":
    main()
