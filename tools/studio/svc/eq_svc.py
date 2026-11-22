"""Еквалайзер: профілі груп і перезапис обраних дублів (профілі — eq.py)."""
from __future__ import annotations

from .. import eq as eq_mod
from .util import StudioError, export_take, take_no


class EqMixin:
    def eq_json(self, cid: str, gid: str) -> dict:
        with self.lock:
            self.groups(cid)
            sel = self.eq.effective_id(cid, gid)
            st = self.store(cid)
            stale = sum(self.is_stale(cid, gid, st.entry(gid, ln.id)) for ln in self.lines(cid, gid))
            return {"selected": sel, "default": eq_mod.default_id(cid, gid, self.eq.presets),
                    "profiles": self.eq.listing(), "stale": stale}

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
                t["game_hash"] = self._game_hash(cid, gid, t, trim)
                st.log(gid, ln.id, f"обробку (EQ «{prof}») застосовано до дубля {take_no(t['file'])}")
                done.append(ln.id)
            if done:
                st.save()
            return {"done": done, "failed": failed, "lines": [self.line_json(cid, gid, ln) for ln in self.lines(cid, gid)]}
