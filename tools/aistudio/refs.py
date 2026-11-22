"""Референси голосу: ЛИШЕ власні дублі користувача. Жорстка етика (ADR 0003), перевіряється кодом.

Дозволено: будь-який власний дубль (затверджений чи ні, будь-якої репліки/юніта ТОГО Ж каталогу) — вибирає користувач.
Типово (ref_takes = None) — автовибір найдовших ЗАТВЕРДЖЕНИХ дублів інших реплік групи.
Недопустимо завжди: ШІ-дубль (`source == "ai"`), видалений, файл поза audio/self-recorded/<каталог>/<група>/, будь-що з `reference*/`
(оригінали Blizzard), шляхи, `..`. Користувач вказує ІМ'Я дубля (`peonyes2.take1.wav`) або `<група>/<ім'я>` — не шлях.
"""
from __future__ import annotations

from pathlib import Path

from studio import aigen
from studio.catalog import duration
from studio.core import Service, StudioError, take_no

from .params import MAX_REFS


class RefError(StudioError):
    """Недозволений референс."""


def is_reference_path(p: str | Path) -> bool:
    """Будь-яка частина шляху `reference*` (оригінали гри) — заборонено."""
    return any(part.lower().startswith("reference") for part in Path(str(p).replace("\\", "/")).parts)


def list_ref_candidates(svc: Service, cid: str, gid: str | None = None, lid: str | None = None, approved_only: bool = False) -> list[dict]:
    """Усі власні дублі каталогу (для вибору в UI): [{take, key, gid, line, text, approved, dur, peak_db, clipped, created,
    same_line}]. `gid` — група поточної репліки (спершу вона), `lid` — поточна репліка (позначка same_line).
    Без ШІ-дублів, видалених і неіснуючих файлів; шлях — лише в межах audio/self-recorded/<каталог>/."""
    out = []
    groups = [g.id for g in svc.groups(cid)]
    groups.sort(key=lambda g: g != gid)
    for g in groups:
        base = svc.takes_dir(cid, g).resolve()
        for ln in svc.lines(cid, g):
            e = svc.store(cid).entry(g, ln.id)
            for t in e["takes"]:
                if t.get("source") == "ai" or t.get("deleted"):
                    continue
                approved = e["approved"] == t["file"]
                if approved_only and not approved:
                    continue
                p = svc.take_path(cid, g, t)
                try:
                    rel = p.resolve().relative_to(base)
                except ValueError:
                    continue
                if not p.is_file() or is_reference_path(rel):
                    continue
                out.append({"take": t["file"], "key": f"{g}/{t['file']}", "gid": g, "line": ln.id, "n": take_no(t["file"]),
                            "text": e["ua_text"] if e["ua_text"] is not None else ln.ua_hint, "approved": approved,
                            "dur": round(duration(p), 3), "peak_db": t.get("peak_db"), "clipped": bool(t.get("clipped", False)),
                            "created": t.get("created"), "same_line": g == gid and ln.id == lid, "path": p, "take_meta": t})
    return out


def public(c: dict) -> dict:
    """Кандидат без внутрішніх полів (шлях на диску) — для JSON-відповіді UI."""
    return {k: v for k, v in c.items() if k not in ("path", "take_meta")}


def validate(svc: Service, cid: str, gid: str, lid: str, requested) -> list[dict]:
    """Імена дублів → записи кандидатів; будь-яке порушення = RefError (нічого не відкидаємо мовчки)."""
    if is_reference_path(cid) or is_reference_path(gid):
        raise RefError("референс не може бути з reference*/ (оригінали гри)")
    cands = list_ref_candidates(svc, cid, gid, lid)
    chosen = []
    for name in requested:
        parts = name.replace("\\", "/").split("/") if isinstance(name, str) else []
        if (not name or len(parts) > 2 or ".." in parts or "\\" in name or any(not x or x.startswith(".") for x in parts)
                or ":" in name):
            raise RefError(f"референс має бути іменем власного дубля, а не шляхом: {name!r}")
        if is_reference_path(name):
            raise RefError(f"заборонено: {name!r} — оригінали гри (reference*/) не можуть бути референсом голосу")
        hit = [c for c in cands if (c["key"] == name if len(parts) == 2 else c["take"] == name)]
        if not hit:
            raise RefError(f"{name}: це не ваш дубль цього каталогу (або це ШІ/видалений дубль)")
        chosen.append(hit[0])           # однакове ім'я в різних групах: перша — з групи репліки
    return chosen


def resolve(svc: Service, cid: str, gid: str, lid: str, requested, tmp: Path) -> list[dict]:
    """Готові wav-референси [{take, audio, text, approved}] (обрізані збереженим trim): вибір користувача або автовибір."""
    tmp.mkdir(parents=True, exist_ok=True)
    if requested is None:
        cands = [c for c in list_ref_candidates(svc, cid, gid, lid, approved_only=True) if c["gid"] == gid and not c["same_line"]]
        cands.sort(key=lambda c: -c["dur"])
        chosen = cands[:aigen.MAX_REFS]
    else:
        chosen = validate(svc, cid, gid, lid, requested)[:MAX_REFS]
    if not chosen:
        raise RefError("немає власних дублів для референсу голосу (автовибір бере затверджені дублі інших реплік групи)")
    out = []
    for i, c in enumerate(chosen):
        dst = tmp / f"ref{i}-{c['take']}"
        if not dst.exists() and not aigen.ref_clip(svc, cid, c["gid"], c["take_meta"], dst):
            raise RefError(f"не вдалося підготувати референс {c['take']}")
        out.append({"take": c["take"], "key": c["key"], "audio": str(dst), "text": c["text"], "approved": c["approved"]})
    return out
