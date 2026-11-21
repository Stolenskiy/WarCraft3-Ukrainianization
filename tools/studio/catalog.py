"""Каталоги реплік — ЄДИНЕ місце, яке знає, ЗВІДКИ беруться репліки для озвучення.

Студія (core.py, server.py, web/) працює з абстракціями:
  Catalog  — набір груп (напр. «Орда — юніти», згодом «Кампанія людей — місія 3»);
  Group    — персонаж/юніт або сцена місії; має характер/тембр;
  Line     — одна репліка: російський оригінал, підказка UA-тексту, куди класти файл у грі.

Як додати нове джерело (інша раса, місії, будівлі) — див. tools/studio/README.md,
розділ «Розширення». Коротко: реалізувати клас із методами groups()/lines() і
додати його в all_catalogs().
"""
from __future__ import annotations

import json
import re
import subprocess
import wave
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

from .paths import ROOT

# раси, що мають референси у reference/units/<race>/ (порядок = порядок у UI)
UNIT_RACES = [("orc", "Орда"), ("human", "Альянс"), ("undead", "Нежить"), ("nightelf", "Нічні ельфи")]

KIND_RE = re.compile(r"(yesattack|yes|what|pissed|ready|warcry|death|attack)(\d*)\.wav$", re.I)
KIND_ORDER = ["yes", "what", "yesattack", "attack", "pissed", "ready", "warcry", "death", None]
KIND_UA = {
    "yes": "наказ", "what": "виклик", "yesattack": "наказ атакувати", "attack": "атака",
    "pissed": "дражнилка", "ready": "готовий", "warcry": "бойовий клич", "death": "смерть",
    None: "інше",
}


@dataclass
class Line:
    id: str                 # унікальний у межах групи (для юнітів — ім'я файлу)
    ref_path: Path          # російський оригінал (референс)
    ref_en: Path | None = None  # англійський оригінал, якщо витягнуто (tools/build_en_refs.py)
    game_rel: str = ""      # шлях відносно кореня гри, напр. Units/orc/peon/peonyes1.wav
    ru: str = ""            # текст оригіналу (транскрипт)
    ru_dur: float = 0.0
    ua_hint: str = ""       # запропонований український текст (з voice bible)
    direction: str = ""     # «як озвучувати»
    kind: str | None = None
    num: int = 0
    no_speech: bool = False  # у референсі немає мови (вирізана вотермарка)

    @property
    def kind_ua(self) -> str:
        return KIND_UA.get(self.kind, "інше")

    @property
    def stem(self) -> str:
        return Path(self.id).stem


@dataclass
class Group:
    id: str
    title: str
    section: str                       # заголовок розділу в UI, напр. «Melee» / «Кампанія»
    traits: list[str] = field(default_factory=list)


# ---------------------------------------------------------------- утиліти
_dur_cache: dict[tuple, float] = {}


def duration(path: Path) -> float:
    """Тривалість wav у секундах (0.0, якщо файлу немає / не читається)."""
    try:
        st = path.stat()
    except OSError:
        return 0.0
    key = (str(path), st.st_mtime_ns, st.st_size)
    if key not in _dur_cache:
        d = 0.0
        try:
            with wave.open(str(path)) as w:
                if w.getframerate():
                    d = w.getnframes() / w.getframerate()
        except Exception:
            try:
                r = subprocess.run(["afinfo", str(path)], capture_output=True, text=True, timeout=10)
                for line in r.stdout.splitlines():
                    if "estimated duration" in line:
                        d = float(line.split(":")[1].strip().split()[0])
            except Exception:
                pass
        _dur_cache[key] = d
    return _dur_cache[key]


def line_kind(fname: str) -> tuple[str | None, int]:
    m = KIND_RE.search(fname)
    return (m.group(1).lower(), int(m.group(2) or 1)) if m else (None, 0)


def _garbage(text: str) -> bool:
    return re.search(r"(.)\1{7,}", text) is not None


# ---------------------------------------------------------------- voice bible
def parse_bible(path: Path) -> dict:
    """docs/voice-bible/<race>.md → {unit: {title, traits, rows{kind: (start, [UA], напрям)}, order}}.

    Формат аркуша описано в docs/voice-bible/README.md. Розділ «Поза melee-обсягом»
    дає назви кампанійних персонажів (рядки `- **id — Назва** ...`).
    """
    units: dict = {}
    if not path.exists():
        return units
    cur, last_trait, campaign = None, False, False
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^###\s+(\w+)\s+—\s+(.+)$", line)
        if m:
            cur = units.setdefault(m.group(1), {"title": m.group(2).strip(), "traits": [], "rows": {},
                                                "campaign": False, "order": len(units)})
            last_trait = False
            continue
        if line.startswith("## "):
            cur, campaign = None, "melee" in line.lower() and "поза" in line.lower()
            continue
        m = re.match(r"^-\s+\*\*(\w+)\s+—\s+([^*]+)\*\*", line)
        if campaign and m:
            units.setdefault(m.group(1), {"title": m.group(2).strip(), "traits": [], "rows": {},
                                          "campaign": True, "order": len(units)})
            continue
        if cur is None:
            continue
        m = re.match(r"^\*\*(Характер|Тембр|Мовна манера|Роль/архетип):\*\*\s*(.+)", line)
        if m:
            cur["traits"].append(f"{m.group(1)}: {m.group(2).strip()}")
            last_trait = True
            continue
        if last_trait and line.strip() and not line.startswith(("**", "|", "#")):
            cur["traits"][-1] += " " + line.strip()
            continue
        last_trait = False
        m = re.match(r"^\|\s*([a-z]+?)(\d*)(?:\s*[–-]\s*(\d+))?\s*\|(.+?)\|(.+?)\|\s*$", line)
        if m and m.group(1) in KIND_UA:
            items = re.findall(r"«([^»]+)»", m.group(4))
            cur["rows"][m.group(1)] = (int(m.group(2) or 1), items, m.group(5).strip())
    return units


def bible_hint(unit: dict | None, fname: str) -> tuple[str, str]:
    """(запропонований UA-текст, як озвучувати) для файлу репліки."""
    if not unit:
        return "", ""
    kind, n = line_kind(fname)
    row = unit["rows"].get(kind)
    if not row:
        return "", ""
    start, items, direction = row
    i = n - start
    if 0 <= i < len(items):
        return items[i], direction
    return (items[0] if len(items) == 1 else ""), direction


# ---------------------------------------------------------------- каталог юнітів раси
class UnitCatalog:
    """Голоси юнітів однієї раси: reference/units/<race>/<unit>/*.wav.

    Тексти: data/transcripts-<race>-<unit>.json (або transcripts-<unit>.json);
    підказки/характер: docs/voice-bible/<race>.md; без мови: data/watermark-quarantine.json.
    Файл для гри: Units/<race>/<unit>/<file>.wav (той самий шлях, що в CASC гри).
    """

    def __init__(self, race: str, race_title: str, root: Path = ROOT) -> None:
        self.race, self.root = race, root
        self.id = f"units-{race}"
        self.title = f"{race_title} — юніти"
        self.ref_root = root / "reference/units" / race
        self.ref_en_root = root / "reference-en/units" / race

    @cached_property
    def bible(self) -> dict:
        return parse_bible(self.root / f"docs/voice-bible/{self.race}.md")

    @cached_property
    def quarantine(self) -> set[str]:
        p = self.root / "data/watermark-quarantine.json"
        if not p.exists():
            return set()
        q = json.loads(p.read_text(encoding="utf-8"))
        return {f["file"] for f in q.get("files", []) if f.get("cleaned_duration_sec", 0) < 0.2}

    def available(self) -> bool:
        return self.ref_root.is_dir()

    def groups(self) -> list[Group]:
        have = sorted(p.name for p in self.ref_root.iterdir() if p.is_dir()) if self.available() else []
        b = self.bible

        def key(u: str):  # спершу аркуші voice bible у їхньому порядку, потім решта
            return (0, b[u]["order"]) if u in b else (1, u)

        out = []
        for u in sorted(have, key=key):
            info = b.get(u)
            campaign = (info is None) or info["campaign"]
            title = info["title"] if info else u
            out.append(Group(u, title, "Кампанія" if campaign else "Melee — юніти й герої",
                             info["traits"] if info else []))
        return out

    def _transcripts(self, unit: str) -> dict:
        for name in (f"transcripts-{self.race}-{unit}.json", f"transcripts-{unit}.json"):
            p = self.root / "data" / name
            if p.exists():
                return json.loads(p.read_text(encoding="utf-8"))
        return {}

    def lines(self, group_id: str) -> list[Line]:
        tr = self._transcripts(group_id)
        binfo = self.bible.get(group_id)
        out = []
        for p in sorted((self.ref_root / group_id).glob("*.wav")):
            info = tr.get(p.name, {})
            ru = (info.get("text") or "").strip()
            if not ru:
                ru = "(транскрипту ще немає — послухайте оригінал)"
            elif _garbage(ru):
                ru = "(без розбірливих слів — крик / звук)"
            hint, direction = bible_hint(binfo, p.name)
            kind, num = line_kind(p.name)
            en = self.ref_en_root / group_id / p.name
            out.append(Line(
                id=p.name, ref_path=p, ref_en=en if en.exists() else None, game_rel=f"Units/{self.race}/{group_id}/{p.name}",
                ru=ru, ru_dur=info.get("duration") or duration(p), ua_hint=hint, direction=direction,
                kind=kind, num=num, no_speech=f"units/{self.race}/{group_id}/{p.name}" in self.quarantine))
        out.sort(key=lambda ln: (KIND_ORDER.index(ln.kind), ln.num, ln.id))
        return out


def all_catalogs(root: Path = ROOT) -> list:
    """Реєстр каталогів. Нове джерело реплік (місії тощо) — додати сюди."""
    cats = [UnitCatalog(r, t, root) for r, t in UNIT_RACES]
    return [c for c in cats if c.available()]
