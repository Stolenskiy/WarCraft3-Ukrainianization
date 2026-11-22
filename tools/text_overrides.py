"""Наші правки поверх upstream-текстів Units/*.txt (data/text-overrides/units.json).

Самих рядків upstream у репозиторії немає (ADR 0006) — лише операції над ними:
  replace: [[було, стало], …]   виправлення в значенні (друкарські помилки); не знайдено — пропуск із приміткою
  append:  текст                дописати в кінець значення (наші пояснення, напр. «чому кнопка сіра»)
  set:     текст                повне значення (лише наш власний переклад: рядок, якого в upstream немає);
                                ключ, якого в секції нема, дописується; нових секцій не створюємо
Формат: {"Units/<файл>.txt": {"<секція>": {"<ключ>": {op: …}}}}; файл/секція/ключ — без урахування регістру.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / "data/text-overrides/units.json"


def load(path: Path | None = None) -> dict:
    p = Path(path or PATH)
    if not p.is_file():
        return {}
    data = json.loads(p.read_text(encoding="utf-8"))
    return {k.lower(): v for k, v in data.items() if not k.startswith("_")}


def for_file(ov: dict, rel: str) -> dict:
    """Правки одного файлу: {секція(lower): {ключ(lower): op}}."""
    secs = ov.get(rel.lower(), {})
    return {s.lower(): {k.lower(): {"section": s, "key": k, **op} for k, op in keys.items()} for s, keys in secs.items()}


def _quoted(v: str) -> bool:
    return len(v) >= 2 and v[0] == v[-1] == '"'


def _edit(value: str, op: dict, where: str, notes: list[str]) -> str:
    if "set" in op:
        s = op["set"]
        return f'"{s}"' if "," in s and not _quoted(s) else s
    q = _quoted(value)
    inner = value[1:-1] if q else value
    for old, new in op.get("replace", []):
        if old in inner:
            inner = inner.replace(old, new)
        else:
            notes.append(f"{where}: «{old}» не знайдено (upstream уже виправив?) — пропущено")
    inner += op.get("append", "")
    return f'"{inner}"' if q or "," in inner else inner


def apply(text: str, ops: dict, rel: str = "") -> tuple[str, int, list[str]]:
    """Застосувати правки до тексту файлу. Повертає (текст, скільки змінено, примітки)."""
    if not ops:
        return text, 0, []
    lines, out, notes = text.splitlines(keepends=True), [], []
    done: set[tuple[str, str]] = set()
    sec = None

    def nl() -> None:                                  # останній рядок файлу може бути без \n
        if out and not out[-1].endswith("\n"):
            out[-1] += "\n"

    def flush(sec_name: str | None) -> None:          # set для ключів, яких у секції не було
        for k, op in (ops.get(sec_name) or {}).items() if sec_name else ():
            if (sec_name, k) not in done and "set" in op:
                nl()
                out.append(f"{op.get('key', k)}={_edit('', op, '', notes)}\n")
                done.add((sec_name, k))

    for ln in lines:
        m = re.match(r"\s*\[(.+?)\]", ln)
        if m:
            flush(sec)
            sec = m.group(1).lower()
        elif sec in ops and "=" in ln and not ln.lstrip().startswith("//"):
            k, v = ln.split("=", 1)
            op = ops[sec].get(k.strip().lower())
            if op is not None:
                end = v[len(v.rstrip("\r\n")):]
                ln = f"{k}={_edit(v.rstrip(chr(13) + chr(10)), op, f'{rel} [{sec}] {k.strip()}', notes)}{end}"
                done.add((sec, k.strip().lower()))
        out.append(ln)
    flush(sec)
    for s, keys in ops.items():                       # нових секцій не створюємо: лише пропуск із приміткою
        for k in keys:
            if (s, k) not in done:
                notes.append(f"{rel} [{s}] {k}: немає в upstream — пропущено")
    return "".join(out), len(done), notes
