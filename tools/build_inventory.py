#!/usr/bin/env python3
"""Build inventory of WC3 voice-over files from a localization sound tree.

Usage:
    python3 -I build_inventory.py <source_root> <out_csv>

source_root: folder containing race dirs (units/, buildings/, ...)
out_csv:     path to write inventory.csv
"""
import csv
import subprocess
import sys
from pathlib import Path

RACES = ["human", "orc", "undead", "nightelf", "naga", "demon", "creeps", "critters", "other"]

# phrase-type extraction from filename suffixes
TYPES = [
    ("yesattack", "confirm_attack"),   # before plain 'yes'!
    ("pissed", "annoyed"),
    ("warcry", "warcry"),
    ("attack", "attack"),
    ("ready", "ready"),
    ("death", "death"),
    ("what", "question"),
    ("yes", "confirm"),
    ("pissed", "annoyed"),
]


def phrase_type(stem: str) -> str:
    low = stem.lower()
    for suffix, label in TYPES:
        if suffix in low:
            return label
    return "other"


def duration(path: Path) -> str:
    try:
        out = subprocess.run(
            ["afinfo", str(path)], capture_output=True, text=True, timeout=10
        ).stdout
        for line in out.splitlines():
            if "estimated duration" in line:
                return line.split(":")[1].strip().split(" ")[0]
    except Exception:
        pass
    return ""


def main() -> None:
    src = Path(sys.argv[1])
    out = Path(sys.argv[2])
    rows = []
    for wav in sorted(src.rglob("*.wav")):
        rel = wav.relative_to(src)
        parts = rel.parts
        category = parts[0] if parts else "?"
        race = parts[0] if parts and parts[0] in RACES else (
            parts[1] if len(parts) > 1 and parts[1] in RACES else ""
        )
        # unit folder: first path component that is not the category/race label
        unit = next(
            (p for p in parts if p not in (category, race) and p != wav.name),
            "",
        )
        stem = wav.stem.lower()
        # unit voice name = filename without trailing type+number
        voice_id = stem
        for suffix, _ in TYPES:
            if suffix in stem:
                voice_id = stem.split(suffix)[0].rstrip("_-0123456789")
                break
        rows.append(
            {
                "file": str(rel),
                "category": category,
                "race": race,
                "unit_folder": unit,
                "voice_id": voice_id,
                "phrase_type": phrase_type(stem),
                "duration_sec": duration(wav),
            }
        )
    with open(out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows to {out}")


if __name__ == "__main__":
    main()
