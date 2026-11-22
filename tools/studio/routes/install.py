"""Встановлення в гру (install_voices): плани, встановлення/відкат, відкриття теки файлів."""
from __future__ import annotations

from pathlib import Path

import install_voices
import opener

from ..catalog import UNIT_RACES
from ..paths import GAME_FILES
from ..svc.util import StudioError
from .registry import Ctx, route


def install_tree(plan: dict, svc) -> dict:
    """Плани install_voices → дерево Раса → Юніт → файли з реальними назвами (запасний варіант — назва теки)."""
    races = {r: t for r, t in UNIT_RACES}
    tree: dict[str, dict] = {}
    for f in plan["files"]:
        parts = f["rel"].split("/")
        race, unit = (parts[1], parts[2]) if len(parts) >= 4 and parts[0].lower() == "units" else ("", "")
        rid = race.lower()
        r = tree.setdefault(rid, {"id": rid, "title": races.get(rid, race or "Інше"), "units": {}})
        if unit not in r["units"]:
            title = unit or "—"
            try:
                title = next((g.title for g in svc.groups(f"units-{rid}") if g.id == unit), title)
            except StudioError:
                pass
            r["units"][unit] = {"id": unit, "title": title, "files": []}
        r["units"][unit]["files"].append({**f, "name": parts[-1]})
    order = [r for r, _ in UNIT_RACES]
    out = sorted(tree.values(), key=lambda r: order.index(r["id"]) if r["id"] in order else 99)
    return {**{k: v for k, v in plan.items() if k != "files"},
            "races": [{**r, "units": list(r["units"].values())} for r in out]}


@route("GET", "/api/install/plan")
def install_plan(c: Ctx):
    v = c.svc.voices_json()
    return {**install_tree(install_voices.plan(), c.svc),
            "authors": [{"id": a["id"], "name": a["name"]} for a in v["authors"]], "choice": v["choice"]}


@route("GET", "/api/uninstall/plan")
def uninstall_plan(c: Ctx):
    return install_tree(install_voices.uninstall_plan(), c.svc)


def _chosen(c: Ctx) -> list[str] | None:
    chosen = c.data.get("files")
    if chosen is not None and not (isinstance(chosen, list) and all(isinstance(x, str) for x in chosen)):
        raise ValueError("files має бути списком рядків")
    return chosen


@route("POST", "/api/install")
def install(c: Ctx):
    return install_voices.apply(files=_chosen(c))


@route("POST", "/api/uninstall")
def uninstall(c: Ctx):
    return install_voices.uninstall(files=_chosen(c))


@route("POST", "/api/open-dir")
def open_dir(c: Ctx):
    d = c.data
    lines = c.svc.lines(d["cid"], d["gid"])  # валідація
    folder = GAME_FILES / Path(lines[0].game_rel).parent
    folder.mkdir(parents=True, exist_ok=True)
    opener.open_dir(folder)
    return {"ok": True}
