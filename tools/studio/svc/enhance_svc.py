"""ШІ-очищення дублів (tools/aistudio/enhance*.py): результат стає НОВИМ дублем поруч з оригіналом."""
from __future__ import annotations

from pathlib import Path

from aistudio import enhance

from ..catalog import duration
from ..paths import MIN_TAKE_SEC
from .util import CLIP_MIN_SAMPLES, StudioError, now, take_no, wav_peak


class EnhanceMixin:
    def take_of(self, cid: str, gid: str, lid: str, file: str) -> dict:
        """Живий (не в кошику) власний дубль; ШІ-варіанти, взяті в дублі, не очищуємо — це не запис."""
        ln = self.line(cid, gid, lid)
        t = self._take(self.store(cid).entry(gid, ln.id), file)
        if t.get("deleted"):
            raise StudioError(f"дубль {take_no(file)} у кошику")
        if t.get("source") == "ai":
            raise StudioError(f"дубль {take_no(file)} згенеровано ШІ — очищують лише власні записи")
        return t

    def take_file(self, cid: str, gid: str, lid: str, file: str) -> Path:
        p = self.take_path(cid, gid, self.take_of(cid, gid, lid, file))
        if not p.is_file():
            raise StudioError(f"файл дубля не знайдено: {file}")
        return p

    def add_enhanced_take(self, cid: str, gid: str, lid: str, src_file: str, raw: Path, engine: str, approve: bool = False) -> dict:
        """raw (48 кГц вихід моделі) → новий дубль: гучність TARGET_LUFS, формат гри; обрізання й темп — як у джерела.
        approve: якщо джерело обране для гри — обрати очищений замість нього. → {new_file, gain_db, approved}."""
        with self.lock:
            ln, st = self.line(cid, gid, lid), self.store(cid)
            e = st.entry(gid, lid)
            src = self.take_of(cid, gid, lid, src_file)
            target = self.next_take_file(cid, gid, ln)
            target.parent.mkdir(parents=True, exist_ok=True)
            gain = enhance.finish(raw, target)
            if duration(target) < MIN_TAKE_SEC:
                target.unlink(missing_ok=True)
                raise StudioError("після очищення запис порожній")
            peak_db, n_clip = wav_peak(target)
            t = {"file": target.name, "created": now(), "deleted": None, "peak_db": peak_db, "clipped": n_clip >= CLIP_MIN_SAMPLES,
                 "source": "enhanced", "engine": engine, "enhanced_from": src_file}
            for k in ("trim", "tempo"):
                if src.get(k):
                    t[k] = src[k]
            e["takes"].append(t)
            st.log(gid, lid, f"ШІ-очищення ({engine}): дубль {take_no(src_file)} → дубль {take_no(target.name)} ({gain:+.1f} дБ)")
            was_approved = e["approved"] == src_file
        if approve and was_approved:
            self.approve(cid, gid, lid, target.name)
        return {"new_file": target.name, "gain_db": gain, "approved": bool(approve and was_approved)}
