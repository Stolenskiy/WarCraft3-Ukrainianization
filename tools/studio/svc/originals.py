"""«Залишити оригінал»: необроблена копія оригіналу в game-files/ і game-files/.originals.json."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import wave
from pathlib import Path

from ..catalog import Line
from ..paths import GAME_FILES, SR
from .util import ORIGINALS_JSON, StudioError, now, take_no


class OriginalsMixin:
    @staticmethod
    def _set_original_mark(ln: Line, info: dict | None) -> None:
        """Додати/прибрати rel у game-files/.originals.json (атомарно)."""
        p = GAME_FILES / ORIGINALS_JSON
        try:
            data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            data = {}
        if info is None:
            if ln.game_rel not in data:
                return
            data.pop(ln.game_rel)
        else:
            data[ln.game_rel] = info
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp, p)

    @staticmethod
    def _install_original(src: Path, dst: Path) -> None:
        """Необроблена копія оригіналу. Wav 22050 Hz mono s16 — байт-у-байт; інакше лише конвертація формату."""
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            with wave.open(str(src), "rb") as w:
                ok = (w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getcomptype()) == (SR, 1, 2, "NONE")
        except (wave.Error, EOFError):
            ok = False
        if ok:
            shutil.copy2(src, dst)
            return
        tmp = dst.with_suffix(".tmp.wav")
        r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
                            "-ar", str(SR), "-ac", "1", "-sample_fmt", "s16", str(tmp)], capture_output=True, timeout=60)
        if r.returncode != 0 or not tmp.exists():
            tmp.unlink(missing_ok=True)
            raise StudioError("не вдалося перетворити оригінал у формат гри (потрібен ffmpeg)")
        os.replace(tmp, dst)

    def keep_original(self, cid: str, gid: str, lid: str, lang: str) -> dict:
        """Оригінал (ru/en) замість дубля: у гру піде необроблений файл, вибір дубля знімається."""
        with self.lock:
            if lang not in ("ru", "en"):
                raise StudioError("мова оригіналу: ru або en")
            ln, st = self.line(cid, gid, lid), self.store(cid)
            src = ln.ref_en if lang == "en" else (ln.ref_path if ln.has_ru else None)
            if src is None or not src.exists():
                raise StudioError("англійського оригіналу немає" if lang == "en" else "російського оригіналу немає")
            e = st.entry(gid, lid)
            self._install_original(src, self.game_path(ln))
            self._set_original_mark(ln, {"lang": lang, "sha256": hashlib.sha256(self.game_path(ln).read_bytes()).hexdigest()})
            if e["approved"]:
                st.log(gid, lid, f"вибір дубля {take_no(e['approved'])} знято: залишено оригінал")
                e["approved"] = None
            e["original"] = {"lang": lang, "ts": now()}
            st.log(gid, lid, f"залишено оригінал ({lang.upper()}) для гри")
            return self._done(cid, gid, ln)

    def clear_original(self, cid: str, gid: str, lid: str) -> dict:
        with self.lock:
            ln, st = self.line(cid, gid, lid), self.store(cid)
            e = st.entry(gid, lid)
            if e["original"]:
                self.game_path(ln).unlink(missing_ok=True)
                self._set_original_mark(ln, None)
                st.log(gid, lid, f"оригінал ({e['original']['lang'].upper()}) прибрано з гри")
                e["original"] = None
            return self._done(cid, gid, ln)
