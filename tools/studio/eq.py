"""Еквалайзер персонажа: пресети (eq_presets.json, у git), профілі користувача (data/studio/eq.json),
перетворення профілю на ffmpeg-фільтри.

Профіль: {name, enabled, gain_db, bands: [{type, freq_hz, gain_db, q}]}; type —
highpass | lowshelf | peaking | highshelf | lowpass. Користувацький файл:
{"profiles": {id: profile}, "assign": {cid: {gid: profile_id}}}. Пресети лише для читання.
Типовий профіль групи: пресет `<раса>-<gid>` (раса — з cid `units-<раса>`), інакше «Нейтральний».
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import uuid
from pathlib import Path

PRESETS_FILE = Path(__file__).resolve().parent / "eq_presets.json"
BAND_TYPES = ("highpass", "lowshelf", "peaking", "highshelf", "lowpass")
NEUTRAL_ID = "neutral"
MAX_BANDS = 8
MAX_GAIN = 12.0


class EqError(Exception):
    """Некоректний профіль чи дія з профілем (показується користувачеві)."""


def _num(v, name: str, lo: float, hi: float) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v:
        raise EqError(f"{name}: очікується число")
    if not lo <= v <= hi:
        raise EqError(f"{name}: {v} поза межами {lo}…{hi}")
    return round(float(v), 2)


def validate(p) -> dict:
    """Перевірити й нормалізувати профіль (повертає чисту копію)."""
    if not isinstance(p, dict):
        raise EqError("профіль має бути об'єктом")
    name = p.get("name")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 60:
        raise EqError("назва профілю: 1–60 символів")
    bands = p.get("bands", [])
    if not isinstance(bands, list) or len(bands) > MAX_BANDS:
        raise EqError(f"смуг має бути не більше {MAX_BANDS}")
    out = []
    for i, b in enumerate(bands, 1):
        if not isinstance(b, dict) or b.get("type") not in BAND_TYPES:
            raise EqError(f"смуга {i}: тип має бути одним із {', '.join(BAND_TYPES)}")
        out.append({"type": b["type"], "freq_hz": _num(b.get("freq_hz"), f"смуга {i}: частота", 20, 20000),
                    "gain_db": _num(b.get("gain_db", 0), f"смуга {i}: підсилення", -MAX_GAIN, MAX_GAIN),
                    "q": _num(b.get("q", 0.71), f"смуга {i}: Q", 0.1, 18)})
    return {"name": name.strip(), "enabled": bool(p.get("enabled", True)),
            "gain_db": _num(p.get("gain_db", 0), "загальне підсилення", -MAX_GAIN, MAX_GAIN), "bands": out}


def _g(x: float) -> str:
    return f"{x:g}"


def to_ffmpeg(profile: dict) -> list[str]:
    """Профіль → список ffmpeg-фільтрів (порядок: смуги, потім volume). Вимкнений/порожній → []."""
    if not profile.get("enabled", True):
        return []
    fl = []
    for b in profile.get("bands", []):
        f, g, q = _g(b["freq_hz"]), _g(b["gain_db"]), _g(b["q"])
        t = b["type"]
        if t in ("highpass", "lowpass"):
            fl.append(f"{t}=f={f}:t=q:w={q}")
        elif t == "peaking":
            if b["gain_db"]:
                fl.append(f"equalizer=f={f}:t=q:w={q}:g={g}")
        elif b["gain_db"]:
            fl.append(f"{'bass' if t == 'lowshelf' else 'treble'}=g={g}:f={f}:t=q:w={q}")
    if profile.get("gain_db"):
        fl.append(f"volume={_g(profile['gain_db'])}dB")
    return fl


def load_presets(path: Path = PRESETS_FILE) -> dict[str, dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))["presets"]
    return {pid: validate(p) for pid, p in raw.items()}


def default_id(cid: str, gid: str, presets: dict) -> str:
    race = cid.removeprefix("units-") if cid.startswith("units-") else None
    pid = f"{race}-{gid}" if race else None
    if pid in presets:
        return pid
    return "orc-base" if race == "orc" and "orc-base" in presets else NEUTRAL_ID


class EqStore:
    """Пресети + користувацькі профілі й призначення. Файл читається щоразу (дрібний, зміни рідкі)."""

    def __init__(self, path: Path, presets: dict | None = None) -> None:
        self.path = path
        self.presets = presets if presets is not None else load_presets()

    def _load(self) -> dict:
        try:
            d = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            d = {}
        if not isinstance(d, dict):
            d = {}
        if not isinstance(d.get("profiles"), dict):
            d["profiles"] = {}
        if not isinstance(d.get("assign"), dict):
            d["assign"] = {}
        return d

    def _save(self, d: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".tmp-eq-", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    def get(self, pid: str) -> dict | None:
        return self.presets.get(pid) or self._load()["profiles"].get(pid)

    def effective_id(self, cid: str, gid: str) -> str:
        pid = self._load()["assign"].get(cid, {}).get(gid)
        return pid if pid and self.get(pid) else default_id(cid, gid, self.presets)

    def effective(self, cid: str, gid: str) -> dict:
        return self.get(self.effective_id(cid, gid)) or self.presets[NEUTRAL_ID]

    def listing(self) -> list[dict]:
        users = self._load()["profiles"]
        return ([{"id": i, "builtin": True, **p} for i, p in self.presets.items()]
                + [{"id": i, "builtin": False, **p} for i, p in users.items()])

    def save_profile(self, profile, pid: str | None = None) -> str:
        """Створити (pid None) або оновити власний профіль; пресети не змінюються."""
        clean = validate(profile)
        if pid in self.presets:
            raise EqError("пресет лише для читання — збережіть як новий профіль")
        d = self._load()
        if pid is None:
            pid = "u-" + uuid.uuid4().hex[:8]
        elif pid not in d["profiles"]:
            raise EqError(f"невідомий профіль {pid}")
        if not re.fullmatch(r"[\w-]+", pid):
            raise EqError("некоректний id профілю")
        d["profiles"][pid] = clean
        self._save(d)
        return pid

    def delete_profile(self, pid: str) -> None:
        if pid in self.presets:
            raise EqError("пресет видалити не можна")
        d = self._load()
        if pid not in d["profiles"]:
            raise EqError(f"невідомий профіль {pid}")
        del d["profiles"][pid]
        for groups in d["assign"].values():
            for gid in [g for g, v in groups.items() if v == pid]:
                del groups[gid]
        self._save(d)

    def assign(self, cid: str, gid: str, pid: str | None) -> None:
        """Призначити профіль групі; None → повернутися до типового."""
        d = self._load()
        if pid is None:
            d["assign"].get(cid, {}).pop(gid, None)
        elif self.get(pid) is None:
            raise EqError(f"невідомий профіль {pid}")
        else:
            d["assign"].setdefault(cid, {})[gid] = pid
        self._save(d)
