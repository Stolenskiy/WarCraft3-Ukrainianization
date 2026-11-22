"""Генерація ШІ-варіантів: клонування ВЛАСНОГО голосу користувача з його затверджених дублів (локально).

Конвеєр (кожна фаза пропускає вже зроблене, тож запуск повторюваний):
  1. завдання: репліка × варіант (seed/температура/стильова підказка з «Як грати»), референси = власні затверджені
     дублі ІНШИХ реплік (обрізані збереженим `trim`) із точним українським текстом;
  2. генерація (Backend.generate — Fish Speech S2-Pro в окремому процесі `.venv-fish`);
  3. обробка як для гри: авто-обрізання тиші + гучність як в оригіналі (proc.*); EQ НЕ застосовується;
  4. метрики: схожість (WavLM x-vector, косинус до власних дублів) і CER (Whisper) → побічний json.
Референси `reference*/` (оригінали Blizzard) НІКОЛИ не стають референсом голосу — лише міряється тривалість.
Бекенди передаються у `run` (у тестах — підмінні); справжній — `FishBackend`/`WhisperCer`.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field, replace
from pathlib import Path

from . import ai, proc
from .catalog import duration
from .core import Service, StudioError, export_take, now
from .paths import ROOT

ENGINE = "fish-s2-pro"
# (seed, temperature, top_p, із стильовою підказкою?) на варіант 1..3
VARIANT_PARAMS = [(1, 0.7, 0.7, False), (2, 0.7, 0.7, True), (3, 0.8, 0.8, True)]
# ключове слово в «Як грати» → вбудований тег Fish Speech
STYLE_TAGS = [("квапливо", "[hurried]"), ("бадьоро", "[cheerful]"), ("зітхом", "[sighing]"), ("запалом", "[excited]"),
              ("образ", "[indignant]"), ("обурення", "[annoyed]"), ("клятву", "[proud]"), ("догідлив", "[eager to please]"),
              ("зачеплений", "[distracted]"), ("комічний", "[playful]"), ("коротко", "[groaning]")]
MAX_REFS = 3
RETRIES = 1


def say(*a) -> None:
    print(*a, flush=True)


def style_tag(direction: str) -> str | None:
    d = (direction or "").lower()
    return next((tag for key, tag in STYLE_TAGS if key in d), None)


def norm(text: str) -> str:
    return " ".join(re.sub(r"[\W_]+", " ", text.lower().replace("’", "'")).split())


def cer(target: str, heard: str) -> float:
    """Частка символьних помилок (Левенштейн / довжина цілі) після нормалізації; може бути > 1 — обрізаємо до 1."""
    a, b = norm(target), norm(heard)
    if not a:
        return 0.0 if not b else 1.0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return round(min(1.0, prev[-1] / len(a)), 3)


@dataclass
class Job:
    cid: str
    gid: str
    lid: str
    stem: str
    k: int
    text: str            # що кажемо (з тегом стилю, якщо є)
    plain: str           # цільовий текст без тегів — для CER
    seed: int
    temperature: float
    top_p: float
    style: str | None
    max_new: int = 512   # ліміт токенів двигуна: репліки короткі, «заблукана» генерація не має тривати хвилинами
    refs: list[dict] = field(default_factory=list)   # [{take, audio, text}]
    out: Path = None  # type: ignore[assignment]
    params: dict | None = None   # параметри ШІ-студії (tools/aistudio/params.py) — лише передаються в побічний json


def ref_clip(svc: Service, cid: str, gid: str, take: dict, dst: Path) -> bool:
    """Власний затверджений дубль з обрізанням → wav-референс (без EQ і вирівнювання гучності)."""
    tr = take.get("trim")
    flt = [f"atrim=start={tr['start']:.3f}:end={tr['end']:.3f},asetpts=PTS-STARTPTS"] if tr else []
    return export_take(svc.take_path(cid, gid, take), dst, flt)


def own_refs(svc: Service, cid: str, gid: str, tmp: Path, exclude: str | None = None) -> list[dict]:
    """Найдовші затверджені власні дублі (крім `exclude`-репліки): [{take, audio, text, line}]."""
    out = []
    for ln in svc.lines(cid, gid):
        e = svc.store(cid).entry(gid, ln.id)
        if not e["approved"] or ln.id == exclude:
            continue
        t = svc._take(e, e["approved"])
        dst = tmp / f"ref-{ln.stem}.wav"
        if dst.exists() or ref_clip(svc, cid, gid, t, dst):
            text = e["ua_text"] if e["ua_text"] is not None else ln.ua_hint
            out.append({"take": t["file"], "audio": str(dst), "text": text, "line": ln.id, "dur": duration(dst)})
    out.sort(key=lambda r: -r["dur"])
    return out[:MAX_REFS]


def plan(svc: Service, cid: str, gid: str, variants: int, tmp: Path, only: list[str] | None = None) -> list[Job]:
    jobs = []
    tmp.mkdir(parents=True, exist_ok=True)
    for ln in svc.lines(cid, gid):
        if only and ln.id not in only and ln.stem not in only:
            continue
        e = svc.store(cid).entry(gid, ln.id)
        plain = (e["ua_text"] if e["ua_text"] is not None else ln.ua_hint).strip()
        if not plain:
            continue
        refs = own_refs(svc, cid, gid, tmp, exclude=ln.id)
        if not refs:
            raise StudioError("немає затверджених власних дублів для референсу голосу")
        for k in range(1, variants + 1):
            seed, temp, top_p, styled = VARIANT_PARAMS[(k - 1) % len(VARIANT_PARAMS)]
            seed += 100 * ((k - 1) // len(VARIANT_PARAMS))
            tag = style_tag(ln.direction) if styled else None
            jobs.append(Job(cid, gid, ln.id, ln.stem, k, f"{tag} {plain}" if tag else plain, plain, seed, temp, top_p,
                            tag, max_new=int(80 + 50 * max(ln.ru_dur, 0.5)),
                            refs=[{"take": r["take"], "audio": r["audio"], "text": r["text"]} for r in refs],
                            out=ai.ai_dir(cid, gid) / f"{ln.stem}.ai{k}.wav"))
    return jobs


def max_dur(ln) -> float:
    """Найдовше допустиме звучання варіанта: далі — збій генерації, а не повільна манера."""
    return max(3 * ln.ru_dur, ln.ru_dur + 2.5)


def postprocess(svc: Service, job: Job, raw: Path) -> bool:
    """Сирий вихід двигуна → файл у форматі гри: авто-обрізання тиші + гучність як в оригіналі; без EQ."""
    ln = svc.line(job.cid, job.gid, job.lid)
    pre = [proc.AUTO_TRIM]
    flt = pre + proc.volume_stage(raw, pre, ln.ref_path)
    job.out.parent.mkdir(parents=True, exist_ok=True)
    return export_take(raw, job.out, flt)


# ---------------------------------------------------------------- справжні бекенди (локальні, у підпроцесах)
def fish_paths() -> dict:
    py = os.environ.get("WC3_FISH_PY") or str(ROOT / ".venv-fish/bin/python")
    return {"py": py, "repo": os.environ.get("WC3_FISH_REPO") or str(ROOT / "tools/fish-speech"),
            "model": os.environ.get("WC3_FISH_MODEL") or str(ROOT / "models/fish-s2-pro")}


def _worker(name: str) -> str:
    return str(Path(__file__).resolve().parent.parent / "ai_engines" / name)


def _run_worker(py: str, worker: str, spec: dict, on_line) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(spec, f)
    try:
        p = subprocess.Popen([py, "-I", worker, f.name], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        for line in p.stdout:
            if line.startswith("{"):
                on_line(json.loads(line))
        if p.wait() != 0:
            raise StudioError(f"робітник {Path(worker).name} завершився з кодом {p.returncode}")
    finally:
        os.unlink(f.name)


class FishBackend:
    """Fish Speech S2-Pro (локально, MPS) + схожість голосу WavLM — обидва в `.venv-fish` основного репозиторію."""
    engine, model = ENGINE, "fish-s2-pro"

    def generate(self, jobs: list[Job], raws: dict[int, Path], log=say) -> None:
        pth = fish_paths()
        spec = {"repo": pth["repo"], "model": pth["model"],
                "jobs": [{"out": str(raws[i]), "text": j.text, "seed": j.seed, "temperature": j.temperature,
                          "top_p": j.top_p, "max_new": j.max_new, "refs": [{"audio": r["audio"], "text": r["text"]} for r in j.refs]}
                         for i, j in enumerate(jobs)]}
        _run_worker(pth["py"], _worker("fish_worker.py"), spec, lambda m: log(f"  fish: {m}"))

    def similarity(self, pairs: list[dict]) -> dict[str, float]:
        out: dict[str, float] = {}
        if pairs:
            _run_worker(fish_paths()["py"], _worker("metrics_worker.py"), {"pairs": pairs},
                        lambda m: out.__setitem__(m["id"], m["similarity"]))
        return out


class WhisperCer:
    """Розбірливість: Whisper (mlx, локально) розпізнає український файл → текст."""

    def transcribe(self, paths: list[Path]) -> dict[str, str]:
        from mlx_whisper import transcribe
        return {str(p): transcribe(str(p), path_or_hf_repo="mlx-community/whisper-large-v3-turbo",
                                   language="uk")["text"].strip() for p in paths}


# ---------------------------------------------------------------- головний цикл
def run(svc: Service, cid: str, gid: str, variants: int = 3, *, backend, asr, only: list[str] | None = None,
        log=say) -> dict:
    """Створює відсутні варіанти й добудовує відсутні метрики. Повертає {made, skipped, filled, secs}."""
    t0, made, skipped = time.time(), 0, 0
    with tempfile.TemporaryDirectory(prefix="wc3ua-ai-") as td:
        tmp = Path(td)
        jobs = plan(svc, cid, gid, variants, tmp, only)
        todo = [j for j in jobs if not (j.out.exists() and ai.read_sidecar(j.out))]
        skipped = len(jobs) - len(todo)
        for attempt in range(RETRIES + 1):          # «заблукана» генерація (надто довга) → ще раз з іншим seed
            if not todo:
                break
            log(f"генерація: {len(todo)} (пропущено готових: {skipped}){f', повтор {attempt}' if attempt else ''}")
            raws = {i: tmp / f"raw{attempt}-{i}.wav" for i in range(len(todo))}
            backend.generate(todo, raws, log)
            failed = []
            for i, j in enumerate(todo):
                if not raws[i].exists() or not postprocess(svc, j, raws[i]):
                    log(f"  пропущено {j.out.name}: двигун не дав звуку")
                    failed.append(replace(j, seed=j.seed + 1000))
                elif duration(j.out) > max_dur(svc.line(cid, gid, j.lid)):
                    log(f"  відхилено {j.out.name}: {duration(j.out):.1f} с — надто довго (генерація збилась)")
                    j.out.unlink(missing_ok=True)
                    failed.append(replace(j, seed=j.seed + 1000))
                else:
                    ai.write_sidecar(j.out, {
                        "ai": True, "engine": backend.engine, "model": backend.model, "seed": j.seed,
                        "temperature": j.temperature, "style": j.style, "ref_takes": [r["take"] for r in j.refs],
                        "text": j.plain, "cer": None, "similarity": None, "dur": round(duration(j.out), 3),
                        "created": now()})
                    made += 1
            todo = failed
        filled = fill_metrics(svc, cid, gid, jobs, backend, asr, tmp, log)
    return {"made": made, "skipped": skipped, "filled": filled, "secs": round(time.time() - t0, 1)}


def fill_metrics(svc: Service, cid: str, gid: str, jobs: list[Job], backend, asr, tmp: Path, log=say) -> int:
    """Схожість і CER для побічних json, де їх ще немає. Схожість — до власних дублів (крім цієї репліки)."""
    need = [(j, ai.read_sidecar(j.out)) for j in jobs if j.out.exists()]
    need = [(j, m) for j, m in need if m is not None and (m.get("cer") is None or m.get("similarity") is None)]
    if not need:
        return 0
    pairs = [{"id": j.out.name, "wav": str(j.out), "refs": [r["audio"] for r in j.refs]} for j, m in need
             if m.get("similarity") is None]
    sims = backend.similarity(pairs)
    heard = asr.transcribe([j.out for j, m in need if m.get("cer") is None])
    for j, m in need:
        if m.get("similarity") is None and j.out.name in sims:
            m["similarity"] = sims[j.out.name]
        if m.get("cer") is None and str(j.out) in heard:
            m["cer"] = cer(j.plain, heard[str(j.out)])
            m["heard"] = heard[str(j.out)]
        ai.write_sidecar(j.out, m)
    log(f"метрики: {len(need)}")
    return len(need)


def main(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="ШІ-варіанти реплік юніта з власним голосом користувача")
    ap.add_argument("--unit", default="peon")
    ap.add_argument("--catalog", default="units-orc")
    ap.add_argument("--variants", type=int, default=3)
    ap.add_argument("--only", nargs="*", help="лише ці репліки (peonyes1 …)")
    a = ap.parse_args(argv)
    from .core import Store
    Store.save = lambda self: None      # генератор лише ЧИТАЄ стан студії (навіть підхоплення «осиротілих» файлів не пишемо)
    svc = Service()
    res = run(svc, a.catalog, a.unit, a.variants, backend=FishBackend(), asr=WhisperCer(), only=a.only)
    print(f"готово: нових {res['made']}, пропущено {res['skipped']}, метрик {res['filled']}, {res['secs']} с")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
