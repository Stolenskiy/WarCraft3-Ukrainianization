"""ШІ-варіанти: «Взяти в дублі» й приховування (генерація — tools/ai_voice.py)."""
from __future__ import annotations

import shutil
from pathlib import Path

from .. import ai as ai_mod
from ..catalog import Line
from .util import CLIP_MIN_SAMPLES, StudioError, now, take_no, wav_peak


class AiMixin:
    def _ai_variant(self, cid: str, gid: str, ln: Line, file: str) -> Path:
        p = ai_mod.ai_path(cid, gid, ln.stem, file)
        if p is None or not p.is_file():
            raise StudioError(f"невідомий ШІ-варіант {file}")
        return p

    def adopt_ai(self, cid: str, gid: str, lid: str, file: str) -> dict:
        """КОПІЮЄ ШІ-варіант у дублі як новий дубль (`source: "ai"`, `engine`), далі — як будь-який дубль
        (обрізання, темп, EQ, «Обрати для гри»). Нумерація власних дублів не порушується (max + 1)."""
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
            e["takes"].append({"file": target.name, "created": now(), "deleted": None, "peak_db": peak_db,
                               "clipped": n_clip >= CLIP_MIN_SAMPLES, "source": "ai",
                               "engine": meta.get("engine"), "ai_file": file})
            meta["adopted"] = target.name
            ai_mod.write_sidecar(src, meta)
            st.log(gid, lid, f"ШІ-варіант {file} ({meta.get('engine')}) взято в дублі як дубль {take_no(target.name)}")
            return self._done(cid, gid, ln)

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
