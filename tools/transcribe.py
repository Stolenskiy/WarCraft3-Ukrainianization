#!/usr/bin/env python3
"""Transcribe Russian reference voice files with mlx-whisper.

Usage:
    .venv/bin/python -I tools/transcribe.py <input_dir> <out_json>
"""
import json
import sys
from pathlib import Path


def main() -> None:
    src = Path(sys.argv[1])
    out = Path(sys.argv[2])
    from mlx_whisper import transcribe

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
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"wrote {len(result)} entries to {out}")


if __name__ == "__main__":
    main()
