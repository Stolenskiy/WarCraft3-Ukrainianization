"""Ядро студії: стан (тексти, дублі, затвердження, журнал) і всі дії над ним.

Не знає ні про UI, ні про джерело реплік (це catalog.py). Модель стану одного каталогу
(data/studio/<catalog>.json):

    {"version": 3, "groups": {<group>: {<line>: {
        "ua_text": str | None,          # None = використовується підказка з каталогу
        "approved": <take file> | None, # цей дубль скопійовано в game-files/<game_rel>
        "takes": [{"file", "created", "deleted": iso | None,    # deleted → лежить у _deleted/
                   "trim": {"start": sec, "end": sec},           # trim — необов'язкове ручне обрізання
                   "tempo": 1.15,                                # tempo — необов'язкове прискорення 0.8–1.3
                   "peak_db": dBFS, "clipped": bool}],           # необов'язкові (старі дублі без них)
        "history": [{"ts", "action"}]}}}}

Інваріанти (перевіряються тестами tests/test_studio_core.py):
  * файл дубля ніколи не перезаписується (номер = max(усі відомі) + 1);
  * видалення = переміщення в _deleted/ (відновлюється), затвердження при цьому знімається;
  * ручне обрізання (trim) не змінює файл дубля — лише копію для гри (ffmpeg atrim ПЕРШИМ у
    _export_filters; авто-обрізання тиші, якщо ввімкнене, діє після нього); зміна trim
    затвердженого дубля одразу перезаписує копію для гри;
  * затверджений дубль завжди має копію в game-files, незатверджений — не має.

Темп (tempo, 0.8–1.3, немає ключа = 1.0): ffmpeg atempo зберігає висоту голосу; файл дубля не
змінюється, зміна темпу затвердженого дубля одразу перезаписує копію для гри (як trim).

Налаштування обробки — data/studio/settings.json {auto_trim, denoise, loudness} (proc.SettingsStore;
GET/POST /api/settings). Ланцюжок копії для гри (_export_filters, ЄДИНИЙ для затвердження, перезапису
й «Як у грі» — Service.preview, кеш data/studio/preview-cache/), порядок строгий:
    ручне обрізання → авто-обрізання тиші → шумоговорення → темп → EQ → вирівнювання гучності
(volume до гучності оригіналу репліки ±18 дБ + alimiter, щоб не кліпувало). Деталі — proc.py.
Параметри trim/auto_trim у запитах — застарілий явний override налаштування auto_trim.
"""
from __future__ import annotations

import array
import datetime as dt
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import wave
from pathlib import Path

import voices

from . import catalog as cat_mod
from . import eq as eq_mod
from . import proc
from .catalog import Line, duration
from .paths import GAME_FILES, MIN_TAKE_SEC, ROOT, SR, STATE_DIR, TAKES_ROOT

PREVIEW_DIR = STATE_DIR / "preview-cache"

TAKE_RE = re.compile(r"\.take(\d+)\.wav$", re.I)


class StudioError(Exception):
    """Помилка, яку варто показати користувачеві."""


def now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def take_no(name: str | None) -> int:
    m = TAKE_RE.search(name or "")
    return int(m.group(1)) if m else 0


def file_iso(p: Path) -> str:
    try:
        return dt.datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds")
    except OSError:
        return now()


def new_entry() -> dict:
    return {"ua_text": None, "approved": None, "takes": [], "history": []}


AUTO_TRIM = proc.AUTO_TRIM


CLIP_LEVEL = 0.98     # |x| ≥ цього (частка повної шкали) — перевантаження
CLIP_MIN_SAMPLES = 3  # одиничний відлік — не кліппінг (передискретизація може «перестрибнути»)


def wav_peak(path: Path) -> tuple[float, int]:
    """(пік у dBFS, кількість відліків з |x| ≥ CLIP_LEVEL) для wav s16; без numpy."""
    with wave.open(str(path), "rb") as w:
        if w.getsampwidth() != 2:
            raise StudioError("очікується 16-бітний WAV")
        data = array.array("h")
        data.frombytes(w.readframes(w.getnframes()))
    if sys.byteorder == "big":
        data.byteswap()
    peak = max((max(data), -min(data)), default=0)
    limit = CLIP_LEVEL * 32768
    clipped = sum(1 for v in data if v >= limit or -v >= limit)
    return (round(20 * math.log10(peak / 32768), 2) if peak else -120.0), clipped


def export_take(src: Path, dst: Path, filters: list[str]) -> bool:
    """Копія дубля для гри: ланцюжок ffmpeg-фільтрів `filters` (через кому) → 22050 Hz mono s16.

    Порожній ланцюжок → звичайна конвертація. False — не вдалося (викликач робить просту копію).
    Фільтри збирає Service._export_filters (ручне обрізання, авто-обрізання тиші, EQ персонажа).
    """
    tmp = dst.with_suffix(".tmp.wav")
    try:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
                            *(["-af", ",".join(filters)] if filters else []),
                            "-ar", str(SR), "-ac", "1", "-sample_fmt", "s16", str(tmp)],
                           capture_output=True, timeout=30)
        if r.returncode == 0 and duration(tmp) >= MIN_TAKE_SEC:
            os.replace(tmp, dst)
            return True
    except Exception:
        pass
    tmp.unlink(missing_ok=True)
    return False


# ---------------------------------------------------------------- стан одного каталогу
class Store:
    def __init__(self, catalog_id: str) -> None:
        self.catalog_id = catalog_id
        self.path = STATE_DIR / f"{catalog_id}.json"
        self.data = {"version": 3, "groups": {}}
        for p in (self.path, self.bak):           # зіпсований основний файл → остання добра копія
            if p.exists():
                try:
                    self.data = json.loads(p.read_text(encoding="utf-8"))
                    break
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
        else:
            if self.path.exists():
                raise StudioError(f"стан {self.path.name} зіпсований, резервної копії немає — "
                                  "відновіть з git-ігнорованого бекапу або видаліть файл")

    @property
    def bak(self) -> Path:
        return self.path.with_suffix(".json.bak")

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".tmp-", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        if self.path.exists():
            shutil.copy2(self.path, self.bak)      # попередня версія — резерв
        os.replace(tmp, self.path)  # атомарно: стан не зіпсується при збої

    def entry(self, group: str, line: str) -> dict:
        e = self.data["groups"].setdefault(group, {}).setdefault(line, new_entry())
        for k, v in new_entry().items():
            e.setdefault(k, v)
        return e

    def log(self, group: str, line: str, action: str) -> None:
        self.entry(group, line)["history"].append({"ts": now(), "action": action})


# ---------------------------------------------------------------- сервіс
class Service:
    """Усі дії студії. Потокобезпечний; стан пишеться на диск після кожної зміни.

    Ідентифікатори: cid — каталог (units-orc), gid — група (peon), lid — репліка (peonyes1.wav).
    """

    def __init__(self, catalogs: list | None = None) -> None:
        self.lock = threading.RLock()
        self.catalogs = {c.id: c for c in (catalogs if catalogs is not None else cat_mod.all_catalogs())}
        self._stores: dict[str, Store] = {}
        self._lines: dict[tuple[str, str], list[Line]] = {}
        self._groups: dict[str, list] = {}
        self.eq = eq_mod.EqStore(STATE_DIR / "eq.json")
        self.settings = proc.SettingsStore(STATE_DIR / "settings.json")

    # ---------- доступ
    def catalog(self, cid: str):
        if cid not in self.catalogs:
            raise StudioError(f"невідомий каталог {cid}")
        return self.catalogs[cid]

    def store(self, cid: str) -> Store:
        self.catalog(cid)
        if cid not in self._stores:
            self._stores[cid] = Store(cid)
        return self._stores[cid]

    def groups(self, cid: str) -> list:
        if cid not in self._groups:
            self._groups[cid] = self.catalog(cid).groups()
        return self._groups[cid]

    def lines(self, cid: str, gid: str) -> list[Line]:
        if gid not in {g.id for g in self.groups(cid)}:
            raise StudioError(f"невідома група {cid}/{gid}")
        if (cid, gid) not in self._lines:
            self._lines[(cid, gid)] = self.catalog(cid).lines(gid)
            self._adopt_orphans(cid, gid)
        return self._lines[(cid, gid)]

    def line(self, cid: str, gid: str, lid: str) -> Line:
        for ln in self.lines(cid, gid):
            if ln.id == lid:
                return ln
        raise StudioError(f"невідома репліка {lid}")

    def takes_dir(self, cid: str, gid: str) -> Path:
        return TAKES_ROOT / cid / gid

    def take_path(self, cid: str, gid: str, t: dict) -> Path:
        d = self.takes_dir(cid, gid)
        return d / "_deleted" / t["file"] if t.get("deleted") else d / t["file"]

    @staticmethod
    def game_path(ln: Line) -> Path:
        return GAME_FILES / ln.game_rel

    @staticmethod
    def _take(e: dict, file: str) -> dict:
        for t in e["takes"]:
            if t["file"] == file:
                return t
        raise StudioError(f"невідомий дубль {file}")

    def _adopt_orphans(self, cid: str, gid: str) -> None:
        """Файли дублів на диску, яких немає в стані (збій, ручне копіювання), — додати."""
        st, lines, added = self.store(cid), self._lines[(cid, gid)], 0
        tdir = self.takes_dir(cid, gid)
        for folder, deleted in ((tdir, False), (tdir / "_deleted", True)):
            for f in sorted(folder.glob("*.wav")) if folder.is_dir() else []:
                ln = next((x for x in lines if f.name.lower().startswith(x.stem.lower() + ".")), None)
                if ln is None:
                    continue
                e = st.entry(gid, ln.id)
                if any(t["file"] == f.name for t in e["takes"]):
                    continue
                e["takes"].append({"file": f.name, "created": file_iso(f),
                                   "deleted": file_iso(f) if deleted else None})
                e["takes"].sort(key=lambda t: t.get("created") or "")
                st.log(gid, ln.id, f"знайдено файл дубля {f.name}")
                added += 1
        if added:
            st.save()

    # ---------- серіалізація для UI
    def progress(self, cid: str, gid: str) -> tuple[int, int]:
        lines = self.lines(cid, gid)
        st = self.store(cid).data["groups"].get(gid, {})
        return sum(1 for ln in lines if st.get(ln.id, {}).get("approved")), len(lines)

    def catalogs_json(self) -> list[dict]:
        with self.lock:
            out = []
            for cid, c in self.catalogs.items():
                gs = []
                for g in self.groups(cid):
                    done, total = self.progress(cid, g.id)
                    gs.append({"id": g.id, "title": g.title, "section": g.section, "traits": g.traits,
                               "done": done, "total": total})
                out.append({"id": cid, "title": c.title, "groups": gs})
            return out

    def line_json(self, cid: str, gid: str, ln: Line) -> dict:
        e = self.store(cid).entry(gid, ln.id)
        takes = []
        for t in e["takes"]:
            p = self.take_path(cid, gid, t)
            takes.append({"file": t["file"], "n": take_no(t["file"]), "created": t.get("created"),
                          "deleted": t.get("deleted"), "exists": p.exists(), "trim": t.get("trim"), "tempo": t.get("tempo") or 1.0,
                          "peak_db": t.get("peak_db"), "clipped": bool(t.get("clipped", False)),
                          "dur": round(duration(p), 3) if p.exists() else 0})
        return {"id": ln.id, "kind": ln.kind, "kind_ua": ln.kind_ua, "ru": ln.ru, "ru_dur": round(ln.ru_dur, 3),
                "has_en": ln.ref_en is not None, "has_ru": ln.has_ru,
                "no_speech": ln.no_speech, "game_rel": ln.game_rel,
                "ua": e["ua_text"] if e["ua_text"] is not None else ln.ua_hint,
                "ua_custom": e["ua_text"] is not None, "ua_hint": ln.ua_hint, "direction": ln.direction,
                "approved": e["approved"], "game_exists": self.game_path(ln).exists(),
                "takes": takes, "history": e["history"][-50:]}

    def group_json(self, cid: str, gid: str) -> dict:
        with self.lock:
            return {"catalog": cid, "group": gid,
                    "lines": [self.line_json(cid, gid, ln) for ln in self.lines(cid, gid)]}

    # ---------- дії (кожна повертає оновлену репліку для UI)
    def _done(self, cid: str, gid: str, ln: Line) -> dict:
        self.store(cid).save()
        return self.line_json(cid, gid, ln)

    def next_take_file(self, cid: str, gid: str, ln: Line) -> Path:
        tdir = self.takes_dir(cid, gid)
        used = [take_no(t["file"]) for t in self.store(cid).entry(gid, ln.id)["takes"]]
        for d in (tdir, tdir / "_deleted"):
            if d.is_dir():
                used += [take_no(f.name) for f in d.glob(f"{ln.stem}.take*.wav")]
        n = max(used, default=0) + 1
        while any((d / f"{ln.stem}.take{n}.wav").exists() for d in (tdir, tdir / "_deleted")):
            n += 1
        return tdir / f"{ln.stem}.take{n}.wav"

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
            prev, e["approved"] = e["approved"], file
            st.log(gid, lid, f"обрано дубль {take_no(file)} для гри"
                   + (f" (замість дубля {take_no(prev)})" if prev and prev != file else ""))
            return self._done(cid, gid, ln)

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

    def _write_game(self, cid: str, gid: str, t: dict, ln: Line, auto_trim: bool | None = None) -> None:
        """Записати копію дубля для гри (увесь ланцюжок _export_filters). Невдача → StudioError, старий файл гри
        лишається; сира копія — лише коли ffmpeg взагалі немає."""
        src, dst = self.take_path(cid, gid, t), self.game_path(ln)
        dst.parent.mkdir(parents=True, exist_ok=True)
        if export_take(src, dst, self._export_filters(cid, gid, t, auto_trim, ln)):
            return
        if shutil.which("ffmpeg") is None:
            shutil.copy2(src, dst)
            return
        raise StudioError("не вдалося підготувати файл для гри: після обрізання лишилось замало звуку — "
                          "змініть межі або вимкніть «Обрізати тишу»")

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

    def audio_path(self, kind: str, cid: str, gid: str, name: str) -> Path:
        """Аудіо лише з відомих місць — шлях ніколи не будується з довільного вводу."""
        with self.lock:
            if kind == "ref":
                return self.line(cid, gid, name).ref_path
            if kind == "ref-en":
                en = self.line(cid, gid, name).ref_en
                if en is None:
                    raise StudioError("англійського оригіналу немає")
                return en
            if kind == "game":
                return self.game_path(self.line(cid, gid, name))
            if kind == "take":
                self.lines(cid, gid)
                for e in self.store(cid).data["groups"].get(gid, {}).values():
                    for t in e["takes"]:
                        if t["file"] == name:
                            return self.take_path(cid, gid, t)
            raise StudioError("невідомий файл")

    # ---------- еквалайзер (профілі — eq.py; змінений профіль НЕ перезаписує файли мовчки)
    def eq_json(self, cid: str, gid: str) -> dict:
        with self.lock:
            self.groups(cid)
            sel = self.eq.effective_id(cid, gid)
            return {"selected": sel, "default": eq_mod.default_id(cid, gid, self.eq.presets),
                    "profiles": self.eq.listing()}

    def _eq(self, fn, *a):
        try:
            return fn(*a)
        except eq_mod.EqError as ex:
            raise StudioError(str(ex)) from ex

    def eq_save(self, cid: str, gid: str, profile: dict, pid: str | None = None, assign: bool = True) -> dict:
        """Створити (pid None) чи оновити власний профіль; новий одразу призначається групі."""
        with self.lock:
            self.groups(cid)
            new = self._eq(self.eq.save_profile, profile, pid)
            if assign:
                self.eq.assign(cid, gid, new)
            return {**self.eq_json(cid, gid), "saved_id": new}

    def eq_delete(self, cid: str, gid: str, pid: str) -> dict:
        with self.lock:
            self._eq(self.eq.delete_profile, pid)
            return self.eq_json(cid, gid)

    def eq_assign(self, cid: str, gid: str, pid: str | None) -> dict:
        with self.lock:
            self.groups(cid)
            self._eq(self.eq.assign, cid, gid, pid)
            return self.eq_json(cid, gid)

    def reexport_group(self, cid: str, gid: str, trim: bool | None = None) -> dict:
        """Перезаписати в game-files усі обрані дублі групи з поточним EQ; запис у журнал кожної репліки."""
        with self.lock:
            st, done, failed = self.store(cid), [], []
            prof = self.eq.get(self.eq.effective_id(cid, gid))["name"]
            for ln in self.lines(cid, gid):
                e = st.entry(gid, ln.id)
                if not e["approved"]:
                    continue
                t = self._take(e, e["approved"])
                src = self.take_path(cid, gid, t)
                if not src.exists() or not export_take(src, self.game_path(ln), self._export_filters(cid, gid, t, trim, ln)):
                    failed.append(ln.id)
                    continue
                st.log(gid, ln.id, f"обробку (EQ «{prof}») застосовано до дубля {take_no(t['file'])}")
                done.append(ln.id)
            if done:
                st.save()
            return {"done": done, "failed": failed, "lines": [self.line_json(cid, gid, ln) for ln in self.lines(cid, gid)]}

    # ---------- налаштування обробки, темп, «Як у грі» (обробка — proc.py)
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

    # ---------- голоси спільноти (voices.py): пакети авторів, локальний вибір, публікація
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
