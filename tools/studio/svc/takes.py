"""Дублі: запис, вибір для гри, кошик, текст."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from ..catalog import Line, duration
from ..paths import MIN_TAKE_SEC, SR
from .util import CLIP_MIN_SAMPLES, StudioError, now, take_no, wav_peak


class TakesMixin:
    def add_take(self, cid: str, gid: str, lid: str, wav_bytes: bytes) -> dict:
        """Зберегти запис (будь-який wav від браузера) як новий дубль у форматі гри."""
        with self.lock:
            ln = self.line(cid, gid, lid)
            if wav_bytes[:4] != b"RIFF" or wav_bytes[8:12] != b"WAVE":
                raise StudioError("очікується WAV")      # ffmpeg не вгадує формат чужих байтів
            target = self.next_take_file(cid, gid, ln)
            target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(wav_bytes)
                raw = Path(f.name)
            try:
                r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "wav", "-i", str(raw),
                                    "-ar", str(SR), "-ac", "1", "-sample_fmt", "s16", str(target)],
                                   capture_output=True, timeout=60)
            finally:
                raw.unlink(missing_ok=True)
            d = duration(target) if target.exists() else 0.0
            if r.returncode != 0 or d < MIN_TAKE_SEC:
                target.unlink(missing_ok=True)
                raise StudioError("запис порожній або закороткий")
            st = self.store(cid)
            peak_db, n_clip = wav_peak(target)
            clipped = n_clip >= CLIP_MIN_SAMPLES
            st.entry(gid, lid)["takes"].append({"file": target.name, "created": now(), "deleted": None,
                                                "peak_db": peak_db, "clipped": clipped})
            st.log(gid, lid, f"записано дубль {take_no(target.name)} ({d:.2f} с, пік {peak_db:.1f} дБ"
                   + (", перевантаження)" if clipped else ")"))
            return self._done(cid, gid, ln)

    def approve(self, cid: str, gid: str, lid: str, file: str, trim: bool | None = None) -> dict:
        with self.lock:
            ln, st = self.line(cid, gid, lid), self.store(cid)
            e = st.entry(gid, lid)
            t = self._take(e, file)
            if t.get("deleted"):
                raise StudioError("спершу відновіть дубль із кошика")
            src = self.take_path(cid, gid, t)
            if not src.exists():
                raise StudioError(f"файл дубля не знайдено: {src.name}")
            self._write_game(cid, gid, t, ln, trim)
            if e["original"]:
                self._set_original_mark(ln, None)
                e["original"] = None
                st.log(gid, lid, "оригінал замінено дублем")
            prev, e["approved"] = e["approved"], file
            st.log(gid, lid, f"обрано дубль {take_no(file)} для гри"
                   + (f" (замість дубля {take_no(prev)})" if prev and prev != file else ""))
            return self._done(cid, gid, ln)
    def _drop_approval(self, cid: str, gid: str, ln: Line, e: dict, reason: str) -> None:
        prev, e["approved"] = e["approved"], None
        self.game_path(ln).unlink(missing_ok=True)
        self.store(cid).log(gid, ln.id, f"{reason} (дубль {take_no(prev)})")

    def unapprove(self, cid: str, gid: str, lid: str) -> dict:
        with self.lock:
            ln = self.line(cid, gid, lid)
            e = self.store(cid).entry(gid, lid)
            if e["approved"]:
                self._drop_approval(cid, gid, ln, e, "вибір для гри скасовано")
            return self._done(cid, gid, ln)

    def delete(self, cid: str, gid: str, lid: str, file: str) -> dict:
        with self.lock:
            ln, st = self.line(cid, gid, lid), self.store(cid)
            e = st.entry(gid, lid)
            t = self._take(e, file)
            if not t.get("deleted"):
                if e["approved"] == file:
                    self._drop_approval(cid, gid, ln, e, "вибір для гри знято через видалення")
                src = self.take_path(cid, gid, t)
                ddir = self.takes_dir(cid, gid) / "_deleted"
                ddir.mkdir(parents=True, exist_ok=True)
                if src.exists():
                    shutil.move(str(src), str(ddir / file))
                t["deleted"] = now()
                st.log(gid, lid, f"дубль {take_no(file)} → кошик")
            return self._done(cid, gid, ln)

    def restore(self, cid: str, gid: str, lid: str, file: str) -> dict:
        with self.lock:
            ln, st = self.line(cid, gid, lid), self.store(cid)
            t = self._take(st.entry(gid, lid), file)
            if t.get("deleted"):
                src, dst = self.take_path(cid, gid, t), self.takes_dir(cid, gid) / file
                if dst.exists():
                    raise StudioError(f"{file} уже є серед активних дублів")
                if src.exists():
                    shutil.move(str(src), str(dst))
                t["deleted"] = None
                st.log(gid, lid, f"дубль {take_no(file)} відновлено з кошика")
            return self._done(cid, gid, ln)

    def set_text(self, cid: str, gid: str, lid: str, text: str) -> dict:
        with self.lock:
            ln, st = self.line(cid, gid, lid), self.store(cid)
            e = st.entry(gid, lid)
            text, cur = text.strip(), (e["ua_text"] if e["ua_text"] is not None else ln.ua_hint)
            if text != cur:
                e["ua_text"] = text
                st.log(gid, lid, f"текст: «{cur}» → «{text}»")
            return self._done(cid, gid, ln)
