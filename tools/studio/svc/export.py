"""Експорт у гру: єдиний ланцюжок ffmpeg, обрізання, темп, налаштування, «Як у грі»."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path

from .. import eq as eq_mod
from .. import proc
from ..catalog import Line, duration
from ..paths import MIN_TAKE_SEC
from .util import AUTO_TRIM, PREVIEW_DIR, StudioError, export_take, take_no


class ExportMixin:
    def _base_filters(self, cid: str, gid: str, take: dict, auto_trim: bool | None = None,
                      settings: dict | None = None) -> list[str]:
        """Ланцюжок до вирівнювання гучності: обрізання → авто-тиша → шумоговорення → темп → EQ."""
        cfg = settings or self.settings.get()
        tr = take.get("trim")
        manual = [f"atrim=start={tr['start']:.3f}:end={tr['end']:.3f},asetpts=PTS-STARTPTS"] if tr else []
        auto = cfg["auto_trim"] if auto_trim is None else auto_trim
        return (manual + ([AUTO_TRIM] if auto else []) + (proc.DENOISE if cfg["denoise"] else [])
                + proc.tempo_filter(take.get("tempo")) + eq_mod.to_ffmpeg(self.eq.effective(cid, gid)))

    def _export_filters(self, cid: str, gid: str, take: dict, auto_trim: bool | None = None,
                        ln: Line | None = None, settings: dict | None = None) -> list[str]:
        """ffmpeg-фільтри копії для гри, у порядку застосування. Точка розширення обробки:
        ручне обрізання → авто-обрізання тиші → шумоговорення → темп → EQ → гучність як в оригіналі.
        auto_trim=None — за налаштуванням; `ln` потрібен для вирівнювання гучності (без нього його немає)."""
        cfg = settings or self.settings.get()
        base = self._base_filters(cid, gid, take, auto_trim, cfg)
        if cfg["loudness"] and ln is not None:
            base += proc.volume_stage(self.take_path(cid, gid, take), base, ln.ref_path)
        return base

    def set_trim(self, cid: str, gid: str, lid: str, file: str, start: float | None, end: float | None,
                 auto_trim: bool | None = None) -> dict:
        """Ручне обрізання початку/кінця дубля (секунди від початку файлу); None, None — скинути.
        Файл дубля не змінюється; затверджений дубль одразу перекопіюється в game-files."""
        with self.lock:
            ln, st = self.line(cid, gid, lid), self.store(cid)
            e = st.entry(gid, lid)
            t = self._take(e, file)
            n, old = take_no(file), t.get("trim")
            if (start is None) != (end is None):
                raise StudioError("потрібні обидві межі обрізання (або жодної)")
            if start is None:
                if t.pop("trim", None) is None:
                    return self._done(cid, gid, ln)
                msg = f"скинуто обрізання дубля {n}"
            else:
                if t.get("deleted"):
                    raise StudioError("спершу відновіть дубль із кошика")
                src = self.take_path(cid, gid, t)
                if not src.exists():
                    raise StudioError(f"файл дубля не знайдено: {src.name}")
                try:
                    start, end = round(float(start), 3), round(float(end), 3)
                except (TypeError, ValueError):
                    raise StudioError("межі обрізання мають бути числами") from None
                dur = duration(src)
                if not (0 <= start < end <= dur + 0.005):
                    raise StudioError(f"межі обрізання мають бути 0 ≤ початок < кінець ≤ {dur:.2f} с")
                end = min(end, round(dur, 3))
                if end - start < MIN_TAKE_SEC:
                    raise StudioError(f"після обрізання лишається менше {MIN_TAKE_SEC} с")
                t["trim"] = {"start": start, "end": end}
                msg = f"обрізано дубль {n}: {start:.2f}–{end:.2f} с"
            if e["approved"] == file:                 # інваріант: копія для гри завжди актуальна
                try:
                    self._write_game(cid, gid, t, ln, auto_trim)
                except StudioError:
                    t.pop("trim", None)
                    if old:
                        t["trim"] = old
                    raise
            st.log(gid, lid, msg)
            return self._done(cid, gid, ln)

    def _game_hash(self, cid: str, gid: str, t: dict, auto_trim: bool | None = None) -> str:
        """Відбиток обробки без вирівнювання гучності: що б сьогодні дало «обрізання → … → EQ» для цього дубля."""
        cfg = self.settings.get()
        key = json.dumps([self._base_filters(cid, gid, t, auto_trim, cfg), cfg["loudness"]], sort_keys=True)
        return hashlib.sha1(key.encode()).hexdigest()[:12]

    def is_stale(self, cid: str, gid: str, e: dict) -> bool:
        """Файл у грі зроблено з іншою обробкою, ніж діє зараз (старі записи без відбитка — не застарілі)."""
        t = next((x for x in e["takes"] if x["file"] == e["approved"]), None) if e["approved"] else None
        return bool(t and t.get("game_hash") and t["game_hash"] != self._game_hash(cid, gid, t))

    def _write_game(self, cid: str, gid: str, t: dict, ln: Line, auto_trim: bool | None = None) -> None:
        """Записати копію дубля для гри (увесь ланцюжок _export_filters). Невдача → StudioError, старий файл гри
        лишається; сира копія — лише коли ffmpeg взагалі немає."""
        src, dst = self.take_path(cid, gid, t), self.game_path(ln)
        dst.parent.mkdir(parents=True, exist_ok=True)
        if export_take(src, dst, self._export_filters(cid, gid, t, auto_trim, ln)):
            t["game_hash"] = self._game_hash(cid, gid, t, auto_trim)
            return
        if shutil.which("ffmpeg") is None:
            shutil.copy2(src, dst)
            return
        raise StudioError("не вдалося підготувати файл для гри: після обрізання лишилось замало звуку — "
                          "змініть межі або вимкніть «Обрізати тишу»")
    def get_settings(self) -> dict:
        return self.settings.get()

    def set_settings(self, patch: dict) -> dict:
        """Змінити налаштування (auto_trim/denoise/loudness). Уже обрані файли не чіпає —
        їх оновлює «Застосувати до обраних дублів» (reexport_group)."""
        with self.lock:
            try:
                return self.settings.update(patch)
            except ValueError as ex:
                raise StudioError(str(ex)) from ex

    def set_tempo(self, cid: str, gid: str, lid: str, file: str, tempo: float | None) -> dict:
        """Прискорення дубля (atempo, висота не змінюється): 0.8–1.3; None або 1.0 — скинути.
        Затверджений дубль одразу перекопіюється в game-files."""
        with self.lock:
            ln, st = self.line(cid, gid, lid), self.store(cid)
            e = st.entry(gid, lid)
            t = self._take(e, file)
            n, old = take_no(file), t.get("tempo")
            if tempo is not None:
                try:
                    tempo = round(float(tempo), 3)
                except (TypeError, ValueError):
                    raise StudioError("темп має бути числом") from None
                if not proc.TEMPO_MIN <= tempo <= proc.TEMPO_MAX:
                    raise StudioError(f"темп має бути в межах {proc.TEMPO_MIN}–{proc.TEMPO_MAX}")
            if tempo is None or tempo == 1.0:
                if t.pop("tempo", None) is None:
                    return self._done(cid, gid, ln)
                msg = f"скинуто темп дубля {n}"
            else:
                if t.get("deleted"):
                    raise StudioError("спершу відновіть дубль із кошика")
                if not self.take_path(cid, gid, t).exists():
                    raise StudioError(f"файл дубля не знайдено: {file}")
                t["tempo"] = tempo
                msg = f"темп дубля {n}: ×{tempo:.2f}"
            if e["approved"] == file:
                try:
                    self._write_game(cid, gid, t, ln)
                except StudioError:
                    t.pop("tempo", None)
                    if old:
                        t["tempo"] = old
                    raise
            st.log(gid, lid, msg)
            return self._done(cid, gid, ln)

    def preview(self, cid: str, gid: str, lid: str, file: str) -> Path:
        """«Як у грі» для будь-якого дубля: той самий ланцюжок і налаштування, що в копії для гри, у кеші
        data/studio/preview-cache/ (ключ — ланцюжок + mtime дубля й оригіналу; найстаріші понад
        proc.PREVIEW_MAX видаляються). Повертає шлях до wav."""
        with self.lock:
            ln = self.line(cid, gid, lid)
            t = self._take(self.store(cid).entry(gid, lid), file)
            src = self.take_path(cid, gid, t)
            if not src.exists():
                raise StudioError(f"файл дубля не знайдено: {file}")
            cfg = self.settings.get()
            base = self._base_filters(cid, gid, t, None, cfg)
            try:
                stamp = (src.stat().st_mtime_ns, ln.ref_path.stat().st_mtime_ns if cfg["loudness"] else 0)
            except OSError:
                raise StudioError("файл оригіналу не знайдено") from None
            key = hashlib.sha1(json.dumps([base, cfg["loudness"], str(src), str(ln.ref_path), stamp]).encode()).hexdigest()
            out = PREVIEW_DIR / f"{key}.wav"
            if out.exists():
                os.utime(out)
                return out
            PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
            if not export_take(src, out, self._export_filters(cid, gid, t, None, ln, cfg)):
                raise StudioError("не вдалося підготувати прослуховування «Як у грі»")
            proc.evict_oldest(PREVIEW_DIR, proc.PREVIEW_MAX)
            return out
