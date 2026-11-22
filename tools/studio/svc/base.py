"""Основа Service: доступ до каталогів/реплік, стан і серіалізація для UI, шляхи аудіо."""
from __future__ import annotations

import threading
from pathlib import Path

from .. import ai as ai_mod
from .. import catalog as cat_mod
from .. import eq as eq_mod
from .. import proc
from ..catalog import Line, duration
from ..paths import GAME_FILES, STATE_DIR, TAKES_ROOT
from .store import Store
from .util import StudioError, file_iso, take_no


class Base:
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
        return sum(1 for ln in lines if st.get(ln.id, {}).get("approved") or st.get(ln.id, {}).get("original")), len(lines)

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
                          "source": t.get("source"), "engine": t.get("engine"),
                          "dur": round(duration(p), 3) if p.exists() else 0})
        return {"id": ln.id, "kind": ln.kind, "kind_ua": ln.kind_ua, "ru": ln.ru, "ru_dur": round(ln.ru_dur, 3),
                "has_en": ln.ref_en is not None, "has_ru": ln.has_ru,
                "no_speech": ln.no_speech, "game_rel": ln.game_rel,
                "ua": e["ua_text"] if e["ua_text"] is not None else ln.ua_hint,
                "ua_custom": e["ua_text"] is not None, "ua_hint": ln.ua_hint, "direction": ln.direction,
                "approved": e["approved"], "original": e["original"], "orig_hint": cat_mod.looks_nonverbal(
                    ln.no_speech, e["ua_text"] if e["ua_text"] is not None else ln.ua_hint, ln.ru),
                "game_exists": self.game_path(ln).exists(), "stale": self.is_stale(cid, gid, e),
                "takes": takes, "ai": ai_mod.list_ai(cid, gid, ln.stem), "history": e["history"][-50:]}

    def group_json(self, cid: str, gid: str) -> dict:
        with self.lock:
            return {"catalog": cid, "group": gid,
                    "lines": [self.line_json(cid, gid, ln) for ln in self.lines(cid, gid)]}

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
            if kind == "ai":                      # ШІ-варіанти: лише файли зі списку репліки (audio/ai/…)
                for ln in self.lines(cid, gid):
                    if (p := ai_mod.ai_path(cid, gid, ln.stem, name)) is not None:
                        return p
            if kind == "take":
                self.lines(cid, gid)
                for e in self.store(cid).data["groups"].get(gid, {}).values():
                    for t in e["takes"]:
                        if t["file"] == name:
                            return self.take_path(cid, gid, t)
            raise StudioError("невідомий файл")
