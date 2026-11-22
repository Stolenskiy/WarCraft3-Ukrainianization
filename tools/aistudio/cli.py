"""CLI ШІ-студії: ai-generate, ai-setup, ai-status, ai-consent (через `python tools/run.py …`)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import config, setup
from .jobs import JobQueue
from .params import GenParams, ParamsError


def load_params(arg: str | None) -> GenParams:
    """`--params` — JSON-рядок або @файл.json."""
    if not arg:
        return GenParams()
    raw = Path(arg[1:]).read_text(encoding="utf-8") if arg.startswith("@") else arg
    try:
        return GenParams.from_dict(json.loads(raw))
    except ValueError as ex:
        if isinstance(ex, ParamsError):
            raise
        raise ParamsError(f"--params: некоректний JSON ({ex})") from ex


def parse_line(s: str) -> tuple[str, str, str]:
    parts = s.split("/")
    if len(parts) != 3 or not all(parts):
        raise ParamsError("--line: <каталог>/<група>/<репліка>, напр. units-orc/peon/peonyes1.wav")
    return parts[0], parts[1], parts[2]


def cmd_generate(a, svc=None, queue=None) -> int:
    try:
        cid, gid, lid = parse_line(a.line)
        p = load_params(a.params)
        if svc is None:
            from studio.core import Service, Store
            Store.save = lambda self: None          # CLI лише ЧИТАЄ стан студії
            svc = Service()
        q = queue or JobQueue(svc)
        rec = q.submit(cid, gid, lid, p)
    except (ParamsError, config.ConsentError, OSError) as ex:
        print(f"ПОМИЛКА: {ex}", file=sys.stderr)
        return 2
    except Exception as ex:      # noqa: BLE001 — RefError/StudioError/EngineError: показуємо текст
        print(f"ПОМИЛКА: {ex}", file=sys.stderr)
        return 2
    for w in rec["warnings"]:
        print("УВАГА:", w)
    print(f"завдання {rec['id']} у черзі ({rec['engine']}, ліцензія результату {rec['license']})")
    if a.no_run:
        return 0
    out = q.run_next()
    if out is None:
        print("GPU зайнятий іншим процесом (студія?) — завдання лишилось у черзі, його виконає студія.")
        return 0
    while out is not None and out["id"] != rec["id"]:      # раніше поставлені завдання йдуть першими (FIFO)
        out = q.run_next()
    final = q.get(rec["id"])
    for r in final["results"]:
        print(f"  {r['file']}: сід {r['seed']}, CER {r['cer']}, схожість {r['similarity']}, {r['dur']} с [ШІ]")
    print(f"стан: {final['state']}" + (f" — {final['error']}" if final["error"] else ""))
    return 0 if final["state"] == "done" else 1


def cmd_setup(a) -> int:
    return setup.setup(accept_license=a.accept_license, skip_download=a.skip_download)


def cmd_enhance_setup(a) -> int:
    from . import enhance
    try:
        enhance.setup()
    except enhance.EnhanceError as ex:
        print("ПОМИЛКА:", ex)
        return 1
    return 0


def cmd_status(a) -> int:
    st = setup.status(deep=a.deep)
    pl = st["platform"]
    print(f"Платформа: {pl['os']} {pl['arch']} — {pl['accelerator']} ({pl['speed']})")
    if pl["warning"]:
        print("  УВАГА:", pl["warning"])
    print(f".venv-fish: {'є' if st['venv'] else 'НЕМАЄ'}   fish-speech: {'є' if st['repo'] else 'НЕМАЄ'}   "
          f"ваги: {'ок, ' + str(round(st['weights']['bytes'] / 1e9, 1)) + ' ГБ' if st['weights']['ok'] else 'НЕ готові ' + str(st['weights']['missing'] + st['weights']['problems'])}")
    if st["imports_ok"] is not None:
        print(f"імпорт torch/fish_speech: {'ок' if st['imports_ok'] else 'ПОМИЛКА'}")
    print(f"згода «власний голос»: {'так' if st['consent'] else 'НІ (ai-consent --accept)'}   ліцензію Fish прийнято: "
          f"{st['license_accepted'] or 'ні'}  ({st['license_url']})")
    print("ГОТОВО" if st["ready"] else "НЕ ГОТОВО: " + ", ".join(st["missing"]))
    return 0 if st["ready"] else 1


def cmd_consent(a) -> int:
    if a.engine:
        from .engines import get_engine
        info = get_engine(a.engine).info
        if not a.accept:
            print(f"{info.title}: потрібен --accept — ваші власні дублі буде вивантажено стороннім сервісом. Вартість: {info.cost_note}")
            return 2
        config.set_engine(info.name, upload_consent=True)
        print(f"Згоду на вивантаження дублів у {info.title} збережено.")
        return 0
    if not a.accept:
        print(config.CONSENT_TEXT + "\nПідтвердіть: python tools/run.py ai-consent --accept")
        return 2
    config.set_consent(True)
    print("Згоду збережено (data/local/settings.json).")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="ai")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate")
    g.add_argument("--line", required=True, help="<каталог>/<група>/<репліка>")
    g.add_argument("--params", help="JSON або @файл.json (GenParams)")
    g.add_argument("--no-run", action="store_true", help="лише поставити в чергу")
    g.set_defaults(fn=cmd_generate)
    s = sub.add_parser("setup")
    s.add_argument("--accept-license", action="store_true")
    s.add_argument("--skip-download", action="store_true")
    s.set_defaults(fn=cmd_setup)
    t = sub.add_parser("status")
    t.add_argument("--deep", action="store_true")
    t.set_defaults(fn=cmd_status)
    c = sub.add_parser("consent")
    c.add_argument("--accept", action="store_true")
    c.add_argument("--engine")
    c.set_defaults(fn=cmd_consent)
    sub.add_parser("enhance-setup").set_defaults(fn=cmd_enhance_setup)
    return ap


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    return a.fn(a)
