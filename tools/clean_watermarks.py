#!/usr/bin/env python3
"""Detect and cut watermark artifacts from Russian reference voice-over.

Usage:
    .venv/bin/python -I tools/clean_watermarks.py [src_dir] [out_dir]

Walks reference/ (default), transcribes each wav once with mlx-whisper
(word timestamps), detects watermark segments (credits/whispers like
"Субтитры сделал DimaTorzok", "Продолжение следует..."), and writes a
cleaned mirror to reference-clean/ (default). Files with no detected
watermark are copied as-is.

Outputs:
    data/watermark-report.csv       per-file report
    data/watermark-quarantine.json  files whose cleaned audio is < 0.15 s
"""
import csv
import json
import re
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / (sys.argv[1] if len(sys.argv) > 1 else "reference")
DST = ROOT / (sys.argv[2] if len(sys.argv) > 2 else "reference-clean")
REPORT = ROOT / "data/watermark-report.csv"
QUARANTINE = ROOT / "data/watermark-quarantine.json"
CHECKPOINT = ROOT / "data/.watermark-transcripts.jsonl"

MODEL = "mlx-community/whisper-large-v3-turbo"
PADDING = 0.15  # seconds cut on each side of a watermark segment
MIN_CLEANED = 0.15  # below this the file counts as watermark-only

# Matched against the lowercased, punctuation-stripped segment text.
# Strong stems are unambiguous watermark markers; matched with a left word
# boundary so they do not fire inside canon words ("недооценивать" contains
# "оценив").
STRONG_PATTERNS = [
    "dima", "torzok", "торзок", "субтитр", "продолжение", "подпиш",
    "лайк", "дизлайк", "донат", "оценив", "до встречи",
]
# Common words that also occur inside canon game lines ("Посмотрите",
# "показывали", "Пока получается"): require a whole-word match AND a strong
# watermark hit elsewhere in the same file (these words never mark a
# watermark on their own in this dataset).
WORD_PATTERNS = ["канал", "смотрите", "видео", "пока"]
_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)


def normalize(text: str) -> str:
    return _PUNCT_RE.sub("", text.lower()).strip()


def find_watermark_segments(result: dict) -> list[dict]:
    """Return segments whose normalized text contains any watermark pattern."""
    scanned = []
    has_strong = False
    for seg in result.get("segments", []):
        norm = normalize(seg.get("text", ""))
        if not norm:
            continue
        strong = [p for p in STRONG_PATTERNS if re.search(rf"\b{p}", norm)]
        has_strong = has_strong or bool(strong)
        scanned.append((seg, norm, strong))

    hits = []
    for seg, norm, strong in scanned:
        matched = list(strong)
        if has_strong and not matched:
            matched = [p for p in WORD_PATTERNS
                       if re.search(rf"\b{p}\b", norm)]
        if matched:
            start, end = seg.get("start", 0.0), seg.get("end", 0.0)
            # Refine with word timestamps when available.
            words = seg.get("words") or []
            if words:
                start = min(start, words[0].get("start", start))
                end = max(end, words[-1].get("end", end))
            hits.append({
                "start": float(start),
                "end": float(end),
                "text": seg.get("text", "").strip(),
                "patterns": matched,
            })
    return hits


def merge_intervals(intervals: list[tuple[float, float]]) -> list[tuple[float, float]]:
    if not intervals:
        return []
    intervals = sorted(intervals)
    out = [list(intervals[0])]
    for s, e in intervals[1:]:
        if s <= out[-1][1]:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return [(s, e) for s, e in out]


def complement_intervals(cuts, duration: float) -> list[tuple[float, float]]:
    keep, cursor = [], 0.0
    for s, e in cuts:
        if s > cursor:
            keep.append((cursor, min(s, duration)))
        cursor = max(cursor, e)
    if cursor < duration:
        keep.append((cursor, duration))
    return [(s, e) for s, e in keep if e - s > 1e-4]


def clean_file(src: Path, dst: Path, hits: list[dict]) -> tuple[str, float, float]:
    """Cut watermark ranges, write to dst. Returns (action, orig_dur, new_dur)."""
    info = sf.info(str(src))
    duration = info.frames / info.samplerate
    cuts = merge_intervals([
        (max(0.0, h["start"] - PADDING), min(duration, h["end"] + PADDING))
        for h in hits
    ])
    keep = complement_intervals(cuts, duration)
    new_dur = sum(e - s for s, e in keep)

    data, sr = sf.read(str(src), dtype="int16", always_2d=True)
    chunks = [data[int(round(s * sr)):int(round(e * sr))] for s, e in keep]
    cleaned = np.concatenate(chunks, axis=0) if chunks else np.empty((0, data.shape[1]), dtype="int16")

    dst.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(dst), cleaned, sr, subtype=info.subtype, format="WAV")

    if new_dur < MIN_CLEANED:
        return "now-empty", duration, new_dur
    return "cleaned", duration, new_dur


def main() -> None:
    from mlx_whisper import transcribe

    wavs = sorted(SRC.rglob("*.wav"))
    print(f"{len(wavs)} wav files under {SRC}", flush=True)

    # Resume support: reuse earlier transcriptions if the run was interrupted.
    done: dict[str, dict] = {}
    if CHECKPOINT.exists():
        for line in CHECKPOINT.read_text().splitlines():
            if line.strip():
                rec = json.loads(line)
                done[rec["file"]] = rec

    DST.mkdir(parents=True, exist_ok=True)
    rows = []
    t0 = time.time()
    with CHECKPOINT.open("a", encoding="utf-8") as ckpt:
        for i, wav in enumerate(wavs):
            rel = str(wav.relative_to(SRC))
            dst = DST / rel

            rec = done.get(rel)
            if rec is None:
                try:
                    result = transcribe(
                        str(wav),
                        path_or_hf_repo=MODEL,
                        language="ru",
                        word_timestamps=True,
                    )
                    rec = {"file": rel, "segments": result.get("segments", [])}
                except Exception as exc:  # transcribe failure: retry once, then copy
                    print(f"TRANSCRIBE FAIL {rel}: {exc}", flush=True)
                    try:
                        result = transcribe(
                            str(wav), path_or_hf_repo=MODEL,
                            language="ru", word_timestamps=True,
                        )
                        rec = {"file": rel, "segments": result.get("segments", [])}
                    except Exception as exc2:
                        print(f"TRANSCRIBE FAIL x2 {rel}: {exc2}", flush=True)
                        rec = {"file": rel, "segments": [], "error": str(exc2)}
                ckpt.write(json.dumps(rec, ensure_ascii=False) + "\n")
                ckpt.flush()

            hits = find_watermark_segments(rec)
            removed_text = " | ".join(
                f"[{','.join(h['patterns'])}] {h['text']}" for h in hits
            )
            try:
                if rec.get("error") or not hits:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(wav, dst)
                    info = sf.info(str(wav))
                    rows.append([rel, "copied", round(info.frames / info.samplerate, 3),
                                 round(info.frames / info.samplerate, 3),
                                 rec.get("error", "") or removed_text])
                else:
                    action, odur, ndur = clean_file(wav, dst, hits)
                    rows.append([rel, action, round(odur, 3), round(ndur, 3), removed_text])
            except Exception as exc:
                print(f"CUT FAIL {rel}: {exc}", flush=True)
                shutil.copy2(wav, dst)
                info = sf.info(str(wav))
                rows.append([rel, "copied", round(info.frames / info.samplerate, 3),
                             round(info.frames / info.samplerate, 3), f"CUT_ERROR: {exc}"])

            if (i + 1) % 50 == 0:
                rate = (i + 1) / (time.time() - t0) * 60
                print(f"{i + 1}/{len(wavs)} ({rate:.0f} files/min)", flush=True)

    # Reports
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    with REPORT.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["file", "action", "original_duration_sec",
                    "cleaned_duration_sec", "removed_text"])
        w.writerows(rows)

    quarantined = [r for r in rows if r[1] == "now-empty"]
    QUARANTINE.write_text(json.dumps({
        "min_cleaned_sec": MIN_CLEANED,
        "count": len(quarantined),
        "files": [
            {"file": r[0], "original_duration_sec": r[2],
             "cleaned_duration_sec": r[3], "removed_text": r[4]}
            for r in quarantined
        ],
    }, ensure_ascii=False, indent=2))

    # Sanity checks
    out_wavs = list(DST.rglob("*.wav"))
    cleaned = sum(1 for r in rows if r[1] == "cleaned")
    copied = sum(1 for r in rows if r[1] == "copied")
    sec_removed = sum(r[2] - r[3] for r in rows if r[1] in ("cleaned", "now-empty"))
    print(f"\nIN {len(wavs)} == OUT {len(out_wavs)}: {len(wavs) == len(out_wavs)}")
    print(f"cleaned={cleaned} copied={copied} now-empty={len(quarantined)}")
    print(f"total audio removed: {sec_removed:.1f} s ({sec_removed/60:.1f} min)")
    print(f"report: {REPORT}\nquarantine: {QUARANTINE}")


if __name__ == "__main__":
    main()
