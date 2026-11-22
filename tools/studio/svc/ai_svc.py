"""ШІ-варіанти: «Взяти в дублі» (з автотривалістю), автовибір найкращого й приховування (генерація — tools/ai_voice.py)."""
from __future__ import annotations

import shutil
from pathlib import Path

from .. import ai as ai_mod
from .. import aifit
from ..catalog import Line, duration
from .util import CLIP_MIN_SAMPLES, StudioError, now, take_no, wav_peak


class AiMixin:
    def _ai_variant(self, cid: str, gid: str, ln: Line, file: str) -> Path:
        p = ai_mod.ai_path(cid, gid, ln.stem, file)
        if p is None or not p.is_file():
            raise StudioError(f"невідомий ШІ-варіант {file}")
        return p

    def adopt_ai(self, cid: str, gid: str, lid: str, file: str, fit: bool = False) -> dict:
        """КОПІЮЄ ШІ-варіант у дублі як новий дубль (`source: "ai"`, `engine`), далі — як будь-який дубль
        (обрізання, темп, EQ, «Обрати для гри»). Нумерація власних дублів не порушується (max + 1).
        `fit` — автотривалість: темп дубля під довжину оригіналу (aifit.fit, ×0.8–×1.25; файл не змінюється)."""
        with self.lock:
            ln, st = self.line(cid, gid, lid), self.store(cid)
            src = self._ai_variant(cid, gid, ln, file)
            meta = ai_mod.read_sidecar(src) or {}
            e = st.entry(gid, lid)
            if any(t["file"] == meta.get("adopted") and not t.get("deleted") for t in e["takes"]):
                raise StudioError(f"цей ШІ-варіант уже взято як дубль {take_no(meta['adopted'])}")
            target = self.next_take_file(cid, gid, ln)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
            peak_db, n_clip = wav_peak(target)
            t = {"file": target.name, "created": now(), "deleted": None, "peak_db": peak_db,
                 "clipped": n_clip >= CLIP_MIN_SAMPLES, "source": "ai", "engine": meta.get("engine"), "ai_file": file}
            f = aifit.fit(duration(target), aifit.target_dur(ln)) if fit else None
            if f and f["tempo"] != 1.0:
                t["tempo"] = f["tempo"]
            e["takes"].append(t)
            meta["adopted"] = target.name
            ai_mod.write_sidecar(src, meta)
            st.log(gid, lid, f"ШІ-варіант {file} ({meta.get('engine')}) взято в дублі як дубль {take_no(target.name)}"
                   + (f"; автотривалість: {f['note']}" if f else ""))
            return self._done(cid, gid, ln)

    def auto_pick_ai(self, cid: str, gid: str, lid: str, among: list[str] | None = None, fit: bool = True) -> dict:
        """Автовибір: найкращий за оцінкою ШІ-варіант (серед `among` — напр. однієї генерації) → дубль «ШІ» → у гру.
        Живий запис має пріоритет: якщо для гри обрано власний дубль або «залишено оригінал», нічого не змінюється (помилка).
        Відповідь — стан репліки + `picked: {file, take, score, tempo}`."""
        if among is not None and (not isinstance(among, list) or not all(isinstance(x, str) for x in among)):
            raise StudioError("among: список імен ШІ-варіантів або null")
        with self.lock:
            ln, st = self.line(cid, gid, lid), self.store(cid)
            e = st.entry(gid, lid)
            cur = next((t for t in e["takes"] if t["file"] == e["approved"]), None)
            if cur is not None and cur.get("source") != "ai":
                raise StudioError("для гри обрано живий дубль — автовибір ШІ його не замінює")
            if e["original"]:
                raise StudioError("для гри залишено оригінал — автовибір ШІ його не замінює")
            vs = [v for v in self.line_json(cid, gid, ln)["ai"] if among is None or v["file"] in among]
            top = min((v for v in vs if v["score"] is not None), key=lambda v: (-v["score"], v["n"]), default=None)
            if top is None:
                raise StudioError("немає оцінених ШІ-варіантів для автовибору")
            take = next((t for t in e["takes"] if t["file"] == top["adopted"] and not t.get("deleted")), None)
            if take is None:
                self.adopt_ai(cid, gid, lid, top["file"], fit=fit)
                take = e["takes"][-1]
            if e["approved"] != take["file"]:
                self.approve(cid, gid, lid, take["file"])
                st.log(gid, lid, f"автовибір: ШІ-варіант {top['file']} (оцінка {top['score']}) → дубль {take_no(take['file'])} у грі")
            return {**self._done(cid, gid, ln), "picked": {"file": top["file"], "take": take["file"], "score": top["score"],
                                                            "tempo": take.get("tempo") or 1.0}}

    def discard_ai(self, cid: str, gid: str, lid: str, file: str) -> dict:
        """Сховати ШІ-варіант (файл лишається на диску, у списку його більше немає)."""
        with self.lock:
            ln = self.line(cid, gid, lid)
            src = self._ai_variant(cid, gid, ln, file)
            meta = ai_mod.read_sidecar(src) or {}
            if not meta.get("discarded"):
                meta["discarded"] = True
                ai_mod.write_sidecar(src, meta)
                self.store(cid).log(gid, lid, f"ШІ-варіант {file} приховано")
            return self._done(cid, gid, ln)
