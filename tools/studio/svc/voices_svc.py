"""Голоси спільноти (voices.py): пакети авторів, локальний вибір, публікація."""
from __future__ import annotations

from pathlib import Path

import voices

from ..paths import ROOT
from .util import StudioError


class VoicesMixin:
    def voices_json(self) -> dict:
        """Автори (разом із "local" — власна game-files/) із покриттям, поточний вибір і запам'ятований нікнейм."""
        with self.lock:
            ids = [voices.LOCAL, *voices.authors(ROOT)]
            return {"authors": [voices.author_info(ROOT, a) for a in ids], "choice": voices.load_choice(ROOT),
                    "nickname": voices.get_nickname(ROOT), "consent_text": voices.CONSENT_TEXT,
                    "license": voices.LICENSE}

    def set_voice_choice(self, data: dict) -> dict:
        """Зберегти вибір (default/race/unit/line — розділ замінюється цілком) і/або нікнейм автора цього комп'ютера."""
        with self.lock:
            try:
                if not isinstance(data, dict):
                    raise voices.VoiceError("очікується об'єкт")
                if data.get("nickname") is not None:
                    voices.set_nickname(ROOT, data["nickname"])
                voices.save_choice(ROOT, {k: v for k, v in data.items() if k in ("default", "race", "unit", "line")})
            except voices.VoiceError as ex:
                raise StudioError(str(ex)) from ex
            return self.voices_json()

    def publish_voice(self, nickname: str | None, consent: bool) -> dict:
        """game-files/ → voices/<нік>/ (FLAC); нікнейм запам'ятовується. Git не викликається — повертаємо підказку команд."""
        with self.lock:
            nick = nickname or voices.get_nickname(ROOT)
            try:
                res = voices.publish(nick, nick, ROOT, consent=consent)
                voices.set_nickname(ROOT, nick)
            except (voices.VoiceError, OSError) as ex:
                raise StudioError(str(ex)) from ex
            return res

    def voice_audio(self, author: str, rel: str) -> Path:
        """wav для прослуховування рядка автора: лише відомий файл із маніфесту (sha збігається) або власний game-files."""
        p = voices.author_path(ROOT, author, rel)
        if p is None:
            raise StudioError("невідомий файл голосу")
        try:
            return voices.stage(p, ROOT) if p.suffix == ".flac" else p
        except voices.VoiceError as ex:
            raise StudioError(str(ex)) from ex
