"""Оцінка, скільки ще чекати на ШІ-генерацію (для смуги прогресу в студії).

Вчиться на власних запусках: двигун повідомляє `{"loaded": с}` (завантаження моделі) і `{"out": …, "sec": с}` (один варіант);
метрики (розпізнавання) міряє черга. Ковзне середнє — у `<теки завдань>/timing.json` по двигунах; без історії — типові значення.
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

DEFAULT = {"load": 30.0, "per": 45.0, "metrics": 4.0}   # с; Fish S2-Pro на Apple Silicon — порядок величин із пілоту
ALPHA = 0.4                                               # вага нового виміру


class Timing:
    def __init__(self, path: Path) -> None:
        self.path, self.lock = Path(path), threading.Lock()
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
            assert isinstance(self.data, dict)
        except (OSError, ValueError, AssertionError):
            self.data = {}

    def est(self, engine: str, defaults: dict[str, float] | None = None) -> dict[str, float]:
        return {**(defaults or DEFAULT), **{k: float(v) for k, v in self.data.get(engine, {}).items() if k in DEFAULT}}

    def learn(self, engine: str, key: str, sec) -> None:
        if key not in DEFAULT or not isinstance(sec, (int, float)) or not 0 < sec < 3600:
            return
        with self.lock:
            cur = self.data.setdefault(engine, {})
            cur[key] = round(sec if key not in cur else (1 - ALPHA) * cur[key] + ALPHA * sec, 2)
            try:
                tmp = self.path.with_suffix(".tmp")
                tmp.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
                os.replace(tmp, self.path)
            except OSError:
                pass                                        # оцінка — не критична


def _job_total(rec: dict, e: dict) -> float:
    n = rec["progress"].get("total") or rec["params"].get("n", 1)
    return e["load"] + n * (e["per"] + e["metrics"])


def _job_left(rec: dict, e: dict, t: float) -> float:
    pr = rec["progress"]
    n, done, phase = pr.get("total") or 1, pr.get("done", 0), pr.get("phase")
    since = t - pr.get("t", t)
    if rec["state"] == "queued" or phase == "queued":
        return _job_total(rec, e)
    if phase == "loading":
        return max(e["load"] * 0.1, e["load"] - since) + n * (e["per"] + e["metrics"])
    if phase == "metrics":
        return max(1.0, n * e["metrics"] - since)
    cur = max(e["per"] * 0.1, e["per"] - since) if done < n else 0.0       # поточний варіант уже частково зроблено
    return cur + max(0, n - done - 1) * e["per"] + n * e["metrics"]


def annotate(jobs: list[dict], timing: Timing, t: float | None = None) -> list[dict]:
    """Додає кожному активному завданню eta = {left: с до кінця, total: оцінка всього завдання, ahead: с на завдання перед ним}."""
    t = time.time() if t is None else t
    ahead = 0.0
    for rec in sorted((r for r in jobs if r["state"] in ("queued", "running")), key=lambda r: (r["state"] != "running", r["seq"])):
        e = timing.est(rec["engine"])
        left = _job_left(rec, e, t)
        rec["eta"] = {"left": round(ahead + left), "total": round(_job_total(rec, e)), "ahead": round(ahead)}
        ahead += left
    return jobs
