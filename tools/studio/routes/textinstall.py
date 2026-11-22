"""Текстовий пакет у вікні «Встановити в гру» (чекбокс «Текст»): сухий прогін у фоновому потоці, потім запис лише за підтвердженням.
Логіка — tools/install_pack.py (prepare + plan_text → apply_text / uninstall_text); тут лише обгортка для UI. Докладніше:
docs/plans/text-install-ui.md. Нічого в гру не пишеться без POST /api/text/apply."""
from __future__ import annotations

import secrets
import threading
from pathlib import Path

import gameconf
import install_pack
import install_voices
import textpack

from ..svc.util import StudioError
from .registry import Ctx, route

ERRORS = (install_pack.PackError, textpack.TextPackError, install_voices.InstallError)
_JOBS: dict[str, dict] = {}
_LOCK = threading.Lock()


def detect_target(game: Path) -> str:
    """Ціль за текою гри: є _retail_ (Reforged) → reforged, інакше classic-1.31."""
    return "reforged" if (Path(game) / "_retail_").is_dir() else "classic-1.31"


def _target(tid: str | None, game: Path) -> dict:
    try:
        return textpack.load_target(tid or detect_target(game))
    except ERRORS as ex:
        raise StudioError(str(ex)) from ex


def _installed(root: Path) -> dict | None:
    try:
        m = install_pack._load(root)
    except (OSError, ValueError):
        return None
    return {"files": len(m["files"]), "source": m.get("source")} if m["files"] else None


def summary(target: dict, root: Path, res, pl: dict) -> dict:
    """Короткий підсумок плану для UI (без шляхів джерел)."""
    hk = res.stats.get("hotkeys", {})
    return {"target": target["id"], "title": target["title"], "status": target["status"], "notes": target.get("notes", ""),
            "root": str(root), "commit": res.source.get("commit"), "variant": res.source.get("variant"),
            "sha256": res.source.get("archive_sha256"), "new": sum(f["status"] == "new" for f in pl["files"]),
            "update": sum(f["status"] == "update" for f in pl["files"]), "same": pl["same"], "total": len(pl["files"]),
            "materialize": len(pl["materialize"]), "skipped": pl["skipped"], "notes_skipped": list(res.skipped),
            "hotkeys": {"markers_added": hk.get("markers_added", 0), "tips_changed": hk.get("tips_changed", 0),
                        "sections_changed": hk.get("sections_changed", 0), "skipped_already": hk.get("skipped_already", 0),
                        "skipped_badkey": hk.get("skipped_badkey", 0)},
            "fonts": res.stats.get("fonts", [])}


@route("GET", "/api/text/targets")
def text_targets(c: Ctx):
    game = gameconf.get_game_root()
    det = detect_target(game)
    out = []
    for t in textpack.all_targets():
        try:
            inst = _installed(install_pack.target_root(t, game))
        except install_pack.PackError:
            inst = None
        out.append({"id": t["id"], "title": t["title"], "status": t["status"], "voice": t.get("voice"), "notes": t.get("notes", ""),
                    "full_dirs": t.get("full_dirs", []), "installed": inst})
    return {"game": str(game), "valid": gameconf.describe()["valid"], "detected": det, "targets": out}


def _run_plan(jid: str, tid: str, full: bool, game: Path) -> None:
    job = _JOBS[jid]
    try:
        target, _, root, res = install_pack.prepare(tid, full, None, game, log=lambda s: job["log"].append(str(s)))
        meta = {**res.source, "repo": textpack.REPO, "target": tid}
        pl = install_pack.plan_text(root, res.files)
        job.update(plan=summary(target, root, res, pl), _res=res, _root=root, _meta=meta, state="ready")
    except ERRORS as ex:
        job.update(state="error", error=str(ex))
    except Exception as ex:      # noqa: BLE001 — фоновий потік не має мовчки вмирати: мережа, диск…
        job.update(state="error", error=f"{type(ex).__name__}: {ex}")


@route("POST", "/api/text/plan")
def text_plan(c: Ctx):
    d = c.data
    game = gameconf.get_game_root()
    target = _target(d.get("target"), game)
    jid = secrets.token_hex(4)
    with _LOCK:
        _JOBS[jid] = {"id": jid, "state": "running", "target": target["id"], "log": [], "plan": None, "error": None}
    threading.Thread(target=_run_plan, args=(jid, target["id"], bool(d.get("full")), game), name="text-plan", daemon=True).start()
    return _public(_JOBS[jid])


def _public(job: dict) -> dict:
    return {k: v for k, v in job.items() if not k.startswith("_")} | {"log": job["log"][-12:]}


@route("GET", "/api/text/job")
def text_job(c: Ctx):
    job = _JOBS.get(c.query.get("id", ""))
    if job is None:
        raise StudioError("невідомий план тексту")
    return _public(job)


@route("POST", "/api/text/apply")
def text_apply(c: Ctx):
    job = _JOBS.get(c.data.get("id", ""))
    if job is None or job["state"] not in ("ready", "applied"):
        raise StudioError("спершу підготуйте план тексту (сухий прогін)")
    if job["state"] == "applied":
        raise StudioError("цей план уже застосовано; підготуйте новий")
    try:
        r = install_pack.apply_text(job["_root"], job["_res"].files, job["_meta"])
    except ERRORS as ex:
        raise StudioError(str(ex)) from ex
    job["state"] = "applied"
    return {"installed": r["installed"], "unchanged": r["unchanged"], "skipped": len(r["skipped"]),
            "rollback": f"python tools/run.py uninstall --target {job['target']} --parts text"}


@route("POST", "/api/text/uninstall")
def text_uninstall(c: Ctx):
    game = gameconf.get_game_root()
    try:
        root = install_pack.target_root(_target(c.data.get("target"), game), game)
        return {"removed": install_pack.uninstall_text(root)["removed"]}
    except ERRORS as ex:
        raise StudioError(str(ex)) from ex
