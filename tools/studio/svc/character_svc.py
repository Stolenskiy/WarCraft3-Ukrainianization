"""Пресет персонажа на юніт (висота, форманти, гроул, простір): стан, пропозиція з voice bible, прослуховування A/B.

Зберігається в стані каталогу: data/studio/<cid>.json → "characters": {gid: preset} (старі файли без ключа — працюють:
пресет = пропозиція з voice bible, вимкнена). Логіка й ffmpeg-фільтри — character.py; місце в ланцюжку — export.py.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from .. import character as ch
from .. import proc
from .util import PREVIEW_DIR, StudioError, export_take


class CharacterMixin:
    def _char_stored(self, cid: str, gid: str) -> dict | None:
        chars = self.store(cid).data.get("characters")
        raw = chars.get(gid) if isinstance(chars, dict) else None
        try:
            return ch.validate(raw) if raw is not None else None
        except ch.CharacterError:
            return None                                   # зіпсований запис → пропозиція з voice bible

    def character_suggestion(self, cid: str, gid: str) -> tuple[dict, list[str], str]:
        """(пропозиція, пояснення, текст «Обробка» з аркуша) — з voice bible раси каталогу."""
        cat = self.catalog(cid)
        race, root = getattr(cat, "race", None), getattr(cat, "root", None)
        info = ch.bible_processing(Path(root) / f"docs/voice-bible/{race}.md").get(gid, {}) if race and root else {}
        preset, why = ch.suggest(race, info.get("proc", ""), info.get("timbre", ""))
        return preset, why, info.get("proc", "")

    def character(self, cid: str, gid: str) -> dict:
        """Чинний пресет групи: збережений або пропозиція з voice bible (вимкнена)."""
        return self._char_stored(cid, gid) or self.character_suggestion(cid, gid)[0]

    def character_filters(self, cid: str, gid: str) -> tuple[list[str], list[str]]:
        """(до EQ, після EQ) для ланцюжка експорту; без збереженого ввімкненого пресета — порожньо (bible не читаємо)."""
        stored = self._char_stored(cid, gid)
        return ch.to_ffmpeg(stored) if stored else ([], [])

    def character_json(self, cid: str, gid: str) -> dict:
        with self.lock:
            lines = self.lines(cid, gid)
            sug, why, bible = self.character_suggestion(cid, gid)
            stored, st = self._char_stored(cid, gid), self.store(cid)
            return {"preset": stored or sug, "custom": stored is not None, "suggestion": sug, "why": why, "bible": bible,
                    "limits": {k: list(v) for k, v in ch.LIMITS.items()},
                    "stale": sum(self.is_stale(cid, gid, st.entry(gid, ln.id)) for ln in lines)}

    def character_set(self, cid: str, gid: str, preset: dict | None) -> dict:
        """Зберегти пресет групи; None — прибрати (знову пропозиція з voice bible, вимкнена). Файли гри не
        перезаписуються — їх оновлює «Оновити файли гри» (/api/eq/reexport), а `stale` показує, скільки відстали."""
        with self.lock:
            self.lines(cid, gid)
            st = self.store(cid)
            if not isinstance(st.data.get("characters"), dict):
                st.data["characters"] = {}
            if preset is None:
                if st.data["characters"].pop(gid, None) is None:
                    return self.character_json(cid, gid)
            else:
                try:
                    st.data["characters"][gid] = ch.validate(preset)
                except ch.CharacterError as ex:
                    raise StudioError(str(ex)) from ex
            st.save()
            return self.character_json(cid, gid)

    def character_audio(self, cid: str, gid: str, lid: str, file: str) -> Path:
        """Дубль (увесь, без обрізання й EQ — їх застосовує браузер) лише з голосом і ефектами персонажа — сторона «A»
        у порівнянні «з пресетом / без». Пресет застосовується навіть вимкнений (щоб почути пропозицію). Кеш — preview-cache."""
        with self.lock:
            self.line(cid, gid, lid)
            t = self._take(self.store(cid).entry(gid, lid), file)
            src = self.take_path(cid, gid, t)
            if not src.exists():
                raise StudioError(f"файл дубля не знайдено: {file}")
            voice, fx = ch.to_ffmpeg({**self.character(cid, gid), "enabled": True})
            key = hashlib.sha1(json.dumps(["character", voice + fx, str(src), src.stat().st_mtime_ns]).encode()).hexdigest()
            out = PREVIEW_DIR / f"char-{key}.wav"
            if out.exists():
                os.utime(out)
                return out
            PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
            if not export_take(src, out, voice + fx):
                raise StudioError("не вдалося підготувати голос персонажа")
            proc.evict_oldest(PREVIEW_DIR, proc.PREVIEW_MAX)
            return out
