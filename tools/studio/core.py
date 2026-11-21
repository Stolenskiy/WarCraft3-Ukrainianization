"""Ядро студії: стан (тексти, дублі, затвердження, журнал) і всі дії над ним.

Не знає ні про UI, ні про джерело реплік (це catalog.py). Модель стану одного каталогу
(data/studio/<catalog>.json):

    {"version": 3, "groups": {<group>: {<line>: {
        "ua_text": str | None,          # None = використовується підказка з каталогу
        "approved": <take file> | None, # цей дубль скопійовано в game-files/<game_rel>
        "takes": [{"file", "created", "deleted": iso | None}],   # deleted → лежить у _deleted/
        "history": [{"ts", "action"}]}}}}

Інваріанти (перевіряються тестами tests/test_studio_core.py):
  * файл дубля ніколи не перезаписується (номер = max(усі відомі) + 1);
  * видалення = переміщення в _deleted/ (відновлюється), затвердження при цьому знімається;
  * затверджений дубль завжди має копію в game-files, незатверджений — не має.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

from . import catalog as cat_mod
from .catalog import Line, duration
from .paths import GAME_FILES, MIN_TAKE_SEC, ROOT, SR, STATE_DIR, TAKES_ROOT

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


def export_trimmed(src: Path, dst: Path) -> bool:
    """Копія для гри без тиші на краях (−45 dB), 22050 Hz mono s16. False — не вдалося."""
    flt = ("silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.08,areverse,"
           "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.12,areverse")
    tmp = dst.with_suffix(".tmp.wav")
    try:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
                            "-af", flt, "-ar", str(SR), "-ac", "1", "-sample_fmt", "s16", str(tmp)],
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
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self._migrate_legacy()

    def _migrate_legacy(self) -> None:
        """Перенести стан і файли студій v1/v2 (лише units-orc). Нічого не видаляє."""
        if self.catalog_id != "units-orc":
            return
        v2 = ROOT / "data/record-studio-orc.json"
        v1 = ROOT / "data/record-session-peon.json"
        groups: dict = {}
        if v2.exists():
            groups = json.loads(v2.read_text(encoding="utf-8")).get("units", {})
        elif v1.exists():
            g = groups.setdefault("peon", {})
            for gname, v in json.loads(v1.read_text(encoding="utf-8")).items():
                e = g.setdefault(gname.lower(), new_entry())
                e["takes"] = [{"file": t, "created": now(), "deleted": None} for t in v.get("takes", [])]
                e["approved"] = v.get("approved")
        # файли дублів: audio/self-recorded/<unit>/ → audio/self-recorded/units-orc/<unit>/
        for gid in list(groups) + ["peon"]:
            old, new = TAKES_ROOT / gid, TAKES_ROOT / self.catalog_id / gid
            if old.is_dir() and not new.exists():
                new.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(old), str(new))
        if groups:
            self.data["groups"] = groups
            for lines in groups.values():
                for e in lines.values():
                    e.setdefault("history", []).append({"ts": now(), "action": "перенесено у студію v3"})
            self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".tmp-", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
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
                          "deleted": t.get("deleted"), "exists": p.exists(),
                          "dur": round(duration(p), 3) if p.exists() else 0})
        return {"id": ln.id, "kind": ln.kind, "kind_ua": ln.kind_ua, "ru": ln.ru, "ru_dur": round(ln.ru_dur, 3),
                "has_en": ln.ref_en is not None,
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
            target = self.next_take_file(cid, gid, ln)
            target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(wav_bytes)
                raw = Path(f.name)
            try:
                r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(raw),
                                    "-ar", str(SR), "-ac", "1", "-sample_fmt", "s16", str(target)],
                                   capture_output=True, timeout=60)
            finally:
                raw.unlink(missing_ok=True)
            d = duration(target) if target.exists() else 0.0
            if r.returncode != 0 or d < MIN_TAKE_SEC:
                target.unlink(missing_ok=True)
                raise StudioError("запис порожній або закороткий")
            st = self.store(cid)
            st.entry(gid, lid)["takes"].append({"file": target.name, "created": now(), "deleted": None})
            st.log(gid, lid, f"записано дубль {take_no(target.name)} ({d:.2f} с)")
            return self._done(cid, gid, ln)

    def approve(self, cid: str, gid: str, lid: str, file: str, trim: bool = True) -> dict:
        with self.lock:
            ln, st = self.line(cid, gid, lid), self.store(cid)
            e = st.entry(gid, lid)
            t = self._take(e, file)
            if t.get("deleted"):
                raise StudioError("спершу відновіть дубль із кошика")
            src = self.take_path(cid, gid, t)
            if not src.exists():
                raise StudioError(f"файл дубля не знайдено: {src.name}")
            dst = self.game_path(ln)
            dst.parent.mkdir(parents=True, exist_ok=True)
            if not (trim and export_trimmed(src, dst)):
                shutil.copy2(src, dst)
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
