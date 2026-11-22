"""ШІ-варіанти реплік: окреме джерело поряд зі своїми дублями (ніколи не змішується з їхньою нумерацією).

Файли: `audio/ai/<cid>/<gid>/<line-stem>.ai<k>.wav` + побічний `<line-stem>.ai<k>.json`:
    {"ai": true, "engine", "model", "seed", "temperature", "style", "ref_takes": [файли своїх дублів],
     "text", "cer": 0..1 | null, "similarity": 0..1 | null, "dur": сек, "created": iso,
     "discarded": bool?, "adopted": <файл дубля>?}
Генерує `tools/ai_voice.py` (`make ai-voice`); тут лише читання/приховування/«Взяти в дублі».
Усі файли — голос ШІ, клонований із власних дублів користувача; студія їх завжди позначає «ШІ».
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .paths import ROOT

AI_ROOT = ROOT / "audio/ai"
AI_RE = re.compile(r"^(?P<stem>.+)\.ai(?P<k>\d+)\.wav$")
SIDECAR_KEYS = ("ai", "engine", "model", "seed", "temperature", "style", "ref_takes", "text", "cer", "similarity",
                "dur", "created")


def ai_dir(cid: str, gid: str) -> Path:
    return AI_ROOT / cid / gid


def sidecar_for(wav: Path) -> Path:
    return wav.with_suffix(".json")


def read_sidecar(wav: Path) -> dict | None:
    try:
        d = json.loads(sidecar_for(wav).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) and d.get("ai") is True else None


def write_sidecar(wav: Path, meta: dict) -> None:
    sidecar_for(wav).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def list_ai(cid: str, gid: str, stem: str, include_discarded: bool = False) -> list[dict]:
    """ШІ-варіанти репліки (за номером k): [{file, n, engine, cer, similarity, dur, style, adopted, discarded, license, seed, refs, params}].
    Файл без валідного побічного json (позначки `ai: true`) не показується."""
    d, out = ai_dir(cid, gid), []
    for p in sorted(d.glob(f"{stem}.ai*.wav")) if d.is_dir() else []:
        m = AI_RE.match(p.name)
        meta = read_sidecar(p)
        if not m or m["stem"] != stem or meta is None or (meta.get("discarded") and not include_discarded):
            continue
        out.append({"file": p.name, "n": int(m["k"]), "engine": meta.get("engine"), "cer": meta.get("cer"),
                    "similarity": meta.get("similarity"), "dur": meta.get("dur"), "style": meta.get("style"),
                    "adopted": meta.get("adopted"), "discarded": bool(meta.get("discarded")),
                    "license": meta.get("license"), "seed": meta.get("seed"), "refs": meta.get("refs"), "params": meta.get("params")})
    return sorted(out, key=lambda v: v["n"])


def ai_path(cid: str, gid: str, stem: str, name: str) -> Path | None:
    """Шлях до відомого ШІ-варіанта репліки; ім'я береться лише зі списку, не з довільного вводу."""
    return next((ai_dir(cid, gid) / v["file"] for v in list_ai(cid, gid, stem, True) if v["file"] == name), None)


def ai_stems(cid: str, gid: str) -> set[str]:
    """Стеми реплік групи, у яких є хоча б один видимий (не прихований) ШІ-варіант — один прохід теки (прогрес, чернетка)."""
    d, out = ai_dir(cid, gid), set()
    for p in d.glob("*.ai*.wav") if d.is_dir() else []:
        m = AI_RE.match(p.name)
        if m and m["stem"] not in out and (meta := read_sidecar(p)) is not None and not meta.get("discarded"):
            out.add(m["stem"])
    return out


def voice_kind(e: dict | None, has_variant: bool) -> str:
    """Чим озвучена репліка (живий запис — пріоритет): live — є власний дубль (обраний чи ні), ai_game — у грі ШІ-дубль,
    kept — свідомо залишено оригінал, ai — лише ШІ (варіант чи ШІ-дубль, не обраний), orig — нічого (у грі ще оригінал)."""
    e = e or {}
    takes = [t for t in e.get("takes", []) if not t.get("deleted")]
    appr = next((t for t in takes if t["file"] == e.get("approved")), None)
    if appr is not None:
        return "ai_game" if appr.get("source") == "ai" else "live"
    if e.get("original"):
        return "kept"
    if any(t.get("source") != "ai" for t in takes):
        return "live"
    return "ai" if has_variant or takes else "orig"
