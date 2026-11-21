#!/usr/bin/env python3
"""Студія запису української озвучки Орди — графічний інтерфейс (tkinter).

Запуск:
    cd ~/Desktop/Projects/wc3-ua-voice
    .venv/bin/python -I tools/record_studio.py

Як працює:
  * угорі — вибір юніта Орди і прогрес;
  * ліворуч — усі репліки юніта (російський текст оригіналу; ✅ = затверджено);
  * праворуч — обрана репліка: російський оригінал (послухати), український
    текст (можна редагувати), запис спроб, список спроб, затвердження.

Нічого не губиться:
  * кожна спроба — окремий файл audio/self-recorded/<юніт>/<репліка>.takeN.wav;
  * «Видалити» переносить спробу в audio/self-recorded/<юніт>/_deleted/ —
    її можна повернути кнопкою «Відновити»;
  * затвердження можна будь-коли змінити або скасувати;
  * затверджена спроба копіюється в game-files/Units/orc/<юніт>/<репліка>.wav
    (той самий шлях, що в грі);
  * усе (тексти, спроби, рішення, журнал дій) — у data/record-studio-orc.json.

Клавіші: Пробіл — запис/стоп; R (К) — російський оригінал;
         L (Д) — остання спроба; ↑/↓ — попередня/наступна репліка.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import tkinter as tk
import wave
from pathlib import Path
from tkinter import messagebox, ttk

ROOT = Path(os.environ.get("WC3UA_ROOT") or Path(__file__).resolve().parent.parent)
RACE = "orc"
REF_ROOT = ROOT / "reference/units" / RACE
TAKES_ROOT = ROOT / "audio/self-recorded"
GAME_ROOT = ROOT / "game-files/Units" / RACE
STATE_FILE = ROOT / f"data/record-studio-{RACE}.json"
LEGACY_STATE = ROOT / "data/record-session-peon.json"
BIBLE = ROOT / f"docs/voice-bible/{RACE}.md"
QUARANTINE = ROOT / "data/watermark-quarantine.json"
MIC = os.environ.get("WC3UA_MIC", ":0")  # avfoundation: ":0" = мікрофон за замовчуванням
SR = 22050
MAX_REC_SEC = 30
MIN_TAKE_SEC = 0.25

TAKE_RE = re.compile(r"\.take(\d+)\.wav$", re.I)
TYPE_RE = re.compile(r"(yesattack|yes|what|pissed|ready|warcry|death|attack)(\d*)\.wav$", re.I)
TYPE_ORDER = ["yes", "what", "yesattack", "attack", "pissed", "ready", "warcry", "death", None]
TYPE_UA = {
    "yes": "наказ", "what": "виклик", "yesattack": "наказ атакувати", "attack": "атака",
    "pissed": "дражнилка", "ready": "готовий", "warcry": "бойовий клич", "death": "смерть",
    None: "інше",
}
MELEE_ORDER = ["peon", "grunt", "headhunter", "wolfrider", "battroll", "witchdoctor", "shaman",
               "spiritwalker", "kotobeast", "wyvernrider", "tauren", "heroblademaster",
               "herofarseer", "herotaurenchieftain", "heroshadowhunter"]
CAMPAIGN_TITLES = {"thrall": "Тралл (кампанія)", "cairne": "Керн (кампанія)",
                   "hellscream": "Ґром Ярий Крик (кампанія)"}

# Українські тексти Роботяги, вже звірені з російським оригіналом
PEON_UA = {
    "peonyes1.wav": "Зроблю.", "peonyes2.wav": "З задоволенням.", "peonyes3.wav": "Так, так!",
    "peonyes4.wav": "Добре.", "peonwhat1.wav": "Угу!", "peonwhat3.wav": "Чого хочеш?",
    "peonwhat4.wav": "Чого треба, хазяїне?", "peonpissed1.wav": "Чого?",
    "peonpissed2.wav": "Не заважай, я зайнятий!", "peonpissed3.wav": "Часу нема!",
    "peonpissed4.wav": "Ти мене з кимось плутаєш!", "peonready1.wav": "Готовий колоти!",
    "peonwarcry1.wav": "А чому б і ні?", "peonyesattack2.wav": "Бий їх!",
    "peonyesattack3.wav": "Спробуємо.",
}

GREEN, GREEN_BG, ORANGE, RED, GREY = "#1a7f37", "#dcf5e3", "#b35900", "#c62828", "#777777"


def now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def short_time(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        t = dt.datetime.fromisoformat(iso)
    except ValueError:
        return iso
    return t.strftime("%H:%M") if t.date() == dt.date.today() else t.strftime("%d.%m %H:%M")


_dur_cache: dict[tuple, float] = {}


def duration(path: Path) -> float:
    """Тривалість wav у секундах (0.0, якщо файлу немає / не читається)."""
    try:
        st = path.stat()
    except OSError:
        return 0.0
    key = (str(path), st.st_mtime_ns, st.st_size)
    if key in _dur_cache:
        return _dur_cache[key]
    d = 0.0
    try:
        with wave.open(str(path)) as w:
            if w.getframerate():
                d = w.getnframes() / w.getframerate()
    except Exception:
        pass
    if d <= 0:
        try:
            r = subprocess.run(["afinfo", str(path)], capture_output=True, text=True, timeout=10)
            for line in r.stdout.splitlines():
                if "estimated duration" in line:
                    d = float(line.split(":")[1].strip().split()[0])
        except Exception:
            pass
    _dur_cache[key] = d
    return d


def phrase_type(fname: str) -> tuple[str | None, int]:
    m = TYPE_RE.search(fname)
    if not m:
        return None, 0
    return m.group(1).lower(), int(m.group(2) or 1)


def looks_like_garbage(text: str) -> bool:
    return not text.strip() or re.search(r"(.)\1{7,}", text) is not None


# ---------------------------------------------------------------- voice bible
def parse_bible() -> dict:
    """{unit: {"title", "traits": [..], "rows": {type: (start, [тексти], напрям)}}}"""
    units: dict = {}
    if not BIBLE.exists():
        return units
    cur = None
    last_trait = False
    for line in BIBLE.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^###\s+(\w+)\s+—\s+(.+)$", line)
        if m:
            cur = units.setdefault(m.group(1), {"title": m.group(2).strip(), "traits": [], "rows": {}})
            last_trait = False
            continue
        if line.startswith("## "):
            cur = None
            continue
        if cur is None:
            continue
        m = re.match(r"^\*\*(Характер|Тембр|Мовна манера):\*\*\s*(.+)", line)
        if m:
            cur["traits"].append(f"{m.group(1)}: {m.group(2).strip()}")
            last_trait = True
            continue
        if last_trait and line.strip() and not line.startswith(("**", "|", "#")):
            cur["traits"][-1] += " " + line.strip()
            continue
        last_trait = False
        m = re.match(r"^\|\s*([a-z]+?)(\d*)(?:\s*[–-]\s*(\d+))?\s*\|(.+?)\|(.+?)\|\s*$", line)
        if m and m.group(1) in TYPE_UA:
            items = re.findall(r"«([^»]+)»", m.group(4))
            cur["rows"][m.group(1)] = (int(m.group(2) or 1), items, m.group(5).strip())
    return units


def bible_hint(bible_unit: dict | None, fname: str) -> tuple[str, str]:
    """(запропонований український текст, як озвучувати) з voice bible."""
    if not bible_unit:
        return "", ""
    t, n = phrase_type(fname)
    row = bible_unit["rows"].get(t)
    if not row:
        return "", ""
    start, items, direction = row
    idx = n - start
    if 0 <= idx < len(items):
        return items[idx], direction
    if len(items) == 1:
        return items[0], direction
    return "", direction


# ---------------------------------------------------------------- дані юнітів
def load_transcripts(unit: str) -> dict:
    for name in (f"transcripts-{RACE}-{unit}.json", f"transcripts-{unit}.json"):
        p = ROOT / "data" / name
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    return {}


def load_quarantine() -> set[str]:
    if not QUARANTINE.exists():
        return set()
    q = json.loads(QUARANTINE.read_text(encoding="utf-8"))
    return {f["file"] for f in q.get("files", []) if f.get("cleaned_duration_sec", 0) < 0.2}


def unit_list(bible: dict) -> list[tuple[str, str]]:
    have = sorted(p.name for p in REF_ROOT.iterdir() if p.is_dir()) if REF_ROOT.exists() else []
    order = [u for u in MELEE_ORDER if u in have] + [u for u in have if u not in MELEE_ORDER]
    out = []
    for u in order:
        title = bible.get(u, {}).get("title") or CAMPAIGN_TITLES.get(u) or u
        if u == "peon":
            title = "Роботяга (робітник)"
        out.append((u, title))
    return out


class Phrase:
    def __init__(self, unit: str, fname: str, ru: str, ru_dur: float, ua_hint: str,
                 direction: str, no_speech: bool):
        self.unit, self.fname, self.ru, self.ru_dur = unit, fname, ru, ru_dur
        self.ua_hint, self.direction, self.no_speech = ua_hint, direction, no_speech
        self.ptype, self.pnum = phrase_type(fname)

    @property
    def stem(self) -> str:
        return self.fname[:-4]

    @property
    def ref_path(self) -> Path:
        return REF_ROOT / self.unit / self.fname

    @property
    def game_path(self) -> Path:
        return GAME_ROOT / self.unit / self.fname


def build_phrases(unit: str, bible: dict, quarantine: set[str]) -> list[Phrase]:
    tr = load_transcripts(unit)
    out = []
    for p in sorted((REF_ROOT / unit).glob("*.wav")):
        f = p.name
        info = tr.get(f, {})
        ru = info.get("text", "")
        if looks_like_garbage(ru):
            ru = "(без розбірливих слів — крик / звук)"
        hint, direction = bible_hint(bible.get(unit), f)
        if unit == "peon" and f in PEON_UA:
            hint = PEON_UA[f]
        no_speech = f"units/{RACE}/{unit}/{f}" in quarantine
        out.append(Phrase(unit, f, ru, info.get("duration") or duration(p), hint, direction, no_speech))
    out.sort(key=lambda ph: (TYPE_ORDER.index(ph.ptype), ph.pnum, ph.fname))
    return out


# ---------------------------------------------------------------- стан
def new_entry() -> dict:
    return {"ua_text": None, "approved": None, "takes": [], "history": []}


def file_iso(p: Path) -> str:
    try:
        return dt.datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds")
    except OSError:
        return now()


class Store:
    """Стан студії: тексти, спроби (активні й видалені), затвердження, журнал."""

    def __init__(self) -> None:
        self.data = {"version": 2, "units": {}}
        if STATE_FILE.exists():
            self.data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            self.data.setdefault("units", {})
        self._migrate_legacy()

    def _migrate_legacy(self) -> None:
        """Перенести прогрес першої версії студії (data/record-session-peon.json)."""
        if "peon" in self.data["units"] or not LEGACY_STATE.exists():
            return
        legacy = json.loads(LEGACY_STATE.read_text(encoding="utf-8"))
        u = self.data["units"].setdefault("peon", {})
        tdir = TAKES_ROOT / "peon"
        for gname, v in legacy.items():
            e = u.setdefault(gname.lower(), new_entry())
            for t in v.get("takes", []):
                e["takes"].append({"file": t, "created": file_iso(tdir / t), "deleted": None})
            if v.get("approved"):
                e["approved"] = v["approved"]
            if v.get("takes"):
                e["history"].append({"ts": now(), "action": "імпорт із першої версії студії"})
        self.save()

    def save(self) -> None:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=STATE_FILE.parent, prefix=".record-studio-", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, STATE_FILE)

    def entry(self, unit: str, fname: str) -> dict:
        e = self.data["units"].setdefault(unit, {}).setdefault(fname, new_entry())
        for k, v in new_entry().items():
            e.setdefault(k, v)
        return e

    def log(self, unit: str, fname: str, action: str) -> None:
        self.entry(unit, fname)["history"].append({"ts": now(), "action": action})

    def adopt_orphans(self, unit: str, phrases: list[Phrase]) -> int:
        """Файли спроб на диску, яких немає в стані (напр. після збою), — додати."""
        tdir = TAKES_ROOT / unit
        added = 0
        for folder, deleted in ((tdir, False), (tdir / "_deleted", True)):
            if not folder.is_dir():
                continue
            for f in sorted(folder.glob("*.wav")):
                ph = next((p for p in phrases if f.name.lower().startswith(p.stem.lower() + ".")), None)
                if ph is None:
                    continue
                e = self.entry(unit, ph.fname)
                if any(t["file"] == f.name for t in e["takes"]):
                    continue
                e["takes"].append({"file": f.name, "created": file_iso(f),
                                   "deleted": file_iso(f) if deleted else None})
                e["takes"].sort(key=lambda t: t["created"])
                self.log(unit, ph.fname, f"знайдено файл спроби {f.name}")
                added += 1
        if added:
            self.save()
        return added


def take_no(name: str) -> int:
    m = TAKE_RE.search(name)
    return int(m.group(1)) if m else 0


# ---------------------------------------------------------------- прокручувана панель
class ScrollFrame(ttk.Frame):
    def __init__(self, master, **kw) -> None:
        super().__init__(master, **kw)
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas)
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._win, width=e.width))
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.vsb.pack(side="right", fill="y")
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._wheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

    def _wheel(self, e) -> None:
        self.canvas.yview_scroll(int(-e.delta) if abs(e.delta) < 10 else int(-e.delta / 120), "units")

    def clear(self) -> None:
        for w in self.inner.winfo_children():
            w.destroy()
        self.canvas.yview_moveto(0)


# ---------------------------------------------------------------- головне вікно
class Studio(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Студія української озвучки — Орда")
        self.geometry("1180x780")
        self.minsize(980, 640)
        self.store = Store()
        self.bible = parse_bible()
        self.quarantine = load_quarantine()
        self.units = unit_list(self.bible)
        self.unit = self.units[0][0] if self.units else ""
        self.phrases: list[Phrase] = []
        self.idx = 0
        self.show_deleted = False
        self.recording = False
        self.rec_proc: subprocess.Popen | None = None
        self.rec_ctx: tuple | None = None
        self.rec_log = None
        self.rec_t0 = 0.0
        self.play_proc: subprocess.Popen | None = None
        self.play_queue: list[Path] = []
        self.text_owner: Phrase | None = None  # репліка, якій належить вміст поля UA
        self.var_autoplay = tk.BooleanVar(value=True)
        self.var_trim = tk.BooleanVar(value=True)
        self._build()
        self._bind_keys()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._load_unit(self.unit)

    # ================================================================ UI
    def _build(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        top = ttk.Frame(self, padding=(10, 8))
        top.grid(row=0, column=0, columnspan=2, sticky="ew")
        ttk.Label(top, text="Юніт:", font=("SF Pro Text", 13, "bold")).pack(side="left")
        self.cmb_unit = ttk.Combobox(top, state="readonly", width=42, font=("SF Pro Text", 13))
        self.cmb_unit.pack(side="left", padx=(6, 14))
        self.cmb_unit.bind("<<ComboboxSelected>>", self._on_unit_selected)
        self.lbl_progress = ttk.Label(top, text="", font=("SF Pro Text", 12))
        self.lbl_progress.pack(side="left")
        ttk.Button(top, text="Відкрити файли для гри", takefocus=False,
                   command=self._open_game_dir).pack(side="right")
        ttk.Checkbutton(top, text="Обрізати тишу для гри", variable=self.var_trim,
                        takefocus=False).pack(side="right", padx=8)
        ttk.Checkbutton(top, text="Слухати одразу після запису", variable=self.var_autoplay,
                        takefocus=False).pack(side="right", padx=8)

        # --- ліва панель: репліки
        left = ttk.Frame(self, padding=(10, 0, 4, 10))
        left.grid(row=1, column=0, sticky="ns")
        left.rowconfigure(1, weight=1)
        ttk.Label(left, text="Репліки (російський оригінал)", font=("SF Pro Text", 11, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 4))
        self.lst = tk.Listbox(left, width=44, activestyle="none", font=("SF Pro Text", 13),
                              selectbackground="#2f6fde", selectforeground="white", exportselection=False)
        self.lst.grid(row=1, column=0, sticky="ns")
        sb = ttk.Scrollbar(left, orient="vertical", command=self.lst.yview)
        sb.grid(row=1, column=1, sticky="ns")
        self.lst.configure(yscrollcommand=sb.set)
        self.lst.bind("<<ListboxSelect>>", self._on_list_select)
        ttk.Label(left, text="✅ затверджено   ⬜ ще ні   · N — кількість спроб",
                  foreground=GREY).grid(row=2, column=0, sticky="w", pady=(4, 0))

        # --- права панель
        right = ttk.Frame(self, padding=(8, 0, 12, 10))
        right.grid(row=1, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        r = 0
        self.lbl_traits = ttk.Label(right, text="", foreground=GREY, wraplength=760, justify="left")
        self.lbl_traits.grid(row=r, column=0, sticky="w"); r += 1
        ttk.Separator(right).grid(row=r, column=0, sticky="ew", pady=6); r += 1

        self.lbl_meta = ttk.Label(right, text="", foreground=GREY)
        self.lbl_meta.grid(row=r, column=0, sticky="w"); r += 1

        ru_row = ttk.Frame(right)
        ru_row.grid(row=r, column=0, sticky="ew", pady=(4, 2)); r += 1
        ttk.Label(ru_row, text="RU", foreground=GREY, font=("SF Pro Text", 12, "bold")).pack(side="left")
        self.lbl_ru = ttk.Label(ru_row, text="", font=("SF Pro Display", 22, "bold"), wraplength=640)
        self.lbl_ru.pack(side="left", padx=10)
        ttk.Button(right, text="▶ Послухати російський оригінал  (R)", takefocus=False,
                   command=self._play_ref).grid(row=r, column=0, sticky="w"); r += 1

        ua_row = ttk.Frame(right)
        ua_row.grid(row=r, column=0, sticky="ew", pady=(12, 0)); r += 1
        ua_row.columnconfigure(1, weight=1)
        ttk.Label(ua_row, text="UA", foreground=GREY, font=("SF Pro Text", 12, "bold")).grid(row=0, column=0)
        self.var_ua = tk.StringVar()
        self.ent_ua = ttk.Entry(ua_row, textvariable=self.var_ua, font=("SF Pro Display", 20))
        self.ent_ua.grid(row=0, column=1, sticky="ew", padx=10)
        self.ent_ua.bind("<Return>", lambda e: (self._save_text(), self.focus_set()))
        self.ent_ua.bind("<Escape>", lambda e: (self._reset_text_field(), self.focus_set()))
        self.ent_ua.bind("<FocusOut>", lambda e: self._save_text())
        self.lbl_text_saved = ttk.Label(ua_row, text="", foreground=GREY)
        self.lbl_text_saved.grid(row=0, column=2)
        self.lbl_direction = ttk.Label(right, text="", foreground="#555", wraplength=760, justify="left")
        self.lbl_direction.grid(row=r, column=0, sticky="w", pady=(4, 0)); r += 1

        # статус затвердження
        self.appr_box = tk.Frame(right, padx=10, pady=6)
        self.appr_box.grid(row=r, column=0, sticky="ew", pady=(10, 4)); r += 1
        self.lbl_appr = tk.Label(self.appr_box, text="", font=("SF Pro Text", 13, "bold"), anchor="w")
        self.lbl_appr.pack(side="left")
        self.btn_unapprove = ttk.Button(self.appr_box, text="Скасувати затвердження", takefocus=False,
                                        command=self._unapprove)
        self.btn_play_game = ttk.Button(self.appr_box, text="▶ Як буде в грі", takefocus=False,
                                        command=self._play_game_file)

        # запис
        rec_row = ttk.Frame(right)
        rec_row.grid(row=r, column=0, sticky="ew", pady=(6, 4)); r += 1
        self.btn_rec = tk.Button(rec_row, text="●  Записати спробу  (Пробіл)", font=("SF Pro Text", 15, "bold"),
                                 fg=RED, padx=14, pady=6, takefocus=0, command=self._toggle_record)
        self.btn_rec.pack(side="left")
        self.lbl_rec = tk.Label(rec_row, text="", font=("SF Pro Text", 14, "bold"), fg=RED)
        self.lbl_rec.pack(side="left", padx=14)

        # спроби
        hdr = ttk.Frame(right)
        hdr.grid(row=r, column=0, sticky="ew", pady=(8, 2)); r += 1
        self.lbl_takes_hdr = ttk.Label(hdr, text="Спроби", font=("SF Pro Text", 13, "bold"))
        self.lbl_takes_hdr.pack(side="left")
        self.btn_toggle_deleted = ttk.Button(hdr, text="", takefocus=False, command=self._toggle_deleted)
        self.btn_toggle_deleted.pack(side="right")
        self.takes = ScrollFrame(right)
        self.takes.grid(row=r, column=0, sticky="nsew"); right.rowconfigure(r, weight=1); r += 1

        # журнал
        ttk.Label(right, text="Журнал дій цієї репліки", foreground=GREY).grid(row=r, column=0, sticky="w",
                                                                              pady=(6, 0)); r += 1
        self.txt_hist = tk.Text(right, height=4, font=("Menlo", 11), foreground="#555", relief="flat",
                                background=self.cget("background"), takefocus=0)
        self.txt_hist.grid(row=r, column=0, sticky="ew"); r += 1

        nav = ttk.Frame(right)
        nav.grid(row=r, column=0, sticky="ew", pady=(6, 0)); r += 1
        ttk.Button(nav, text="◀ Попередня", takefocus=False, command=lambda: self._step(-1)).pack(side="left")
        ttk.Button(nav, text="Наступна ▶", takefocus=False, command=lambda: self._step(1)).pack(side="left", padx=6)
        ttk.Button(nav, text="Наступна незатверджена ▶▶", takefocus=False,
                   command=self._next_unapproved).pack(side="left")
        ttk.Label(nav, text="Пробіл — запис/стоп · R — оригінал · L — остання спроба · ↑/↓ — репліки",
                  foreground=GREY).pack(side="right")

        self.cmb_unit["values"] = [self._unit_label(u, t) for u, t in self.units]

    def _bind_keys(self) -> None:
        self.bind_all("<KeyPress>", self._on_key)

    def _on_key(self, e) -> str | None:
        try:
            focus = self.focus_get()
        except (KeyError, tk.TclError):  # macOS: popdown Combobox
            return None
        if isinstance(focus, (ttk.Entry, tk.Entry, ttk.Combobox)):
            return None
        k = e.keysym.lower()
        ch = (e.char or "").lower()
        if k == "space":
            self._toggle_record()
            return "break"
        if self.recording:
            return None
        if ch in ("r", "к"):
            self._play_ref()
        elif ch in ("l", "д"):
            self._play_last_take()
        elif k in ("down", "up"):
            self._step(1 if k == "down" else -1)
            return "break"
        return None

    # ================================================================ юніти
    def _unit_label(self, unit: str, title: str) -> str:
        done, total = self._unit_progress(unit)
        return f"{title}  [{unit}]  —  {done}/{total}"

    def _unit_progress(self, unit: str) -> tuple[int, int]:
        files = [p.name for p in (REF_ROOT / unit).glob("*.wav")]
        st = self.store.data["units"].get(unit, {})
        return sum(1 for f in files if st.get(f, {}).get("approved")), len(files)

    def _on_unit_selected(self, _e=None) -> None:
        i = self.cmb_unit.current()
        if self.recording or i < 0:
            return
        self._load_unit(self.units[i][0])

    def _load_unit(self, unit: str) -> None:
        if not unit:
            messagebox.showerror("Немає референсів", f"Не знайдено {REF_ROOT}")
            return
        self._save_text()
        self.text_owner = None
        self.unit = unit
        self.phrases = build_phrases(unit, self.bible, self.quarantine)
        self.store.adopt_orphans(unit, self.phrases)
        self.cmb_unit.current([u for u, _ in self.units].index(unit))
        b = self.bible.get(unit)
        self.lbl_traits.config(text="\n".join(b["traits"]) if b else "Аркуша у voice bible ще немає.")
        self._refresh_list()
        first = next((i for i, p in enumerate(self.phrases) if not self._entry(p)["approved"]), 0)
        self._select(first)

    # ================================================================ список реплік
    def _entry(self, ph: Phrase | None = None) -> dict:
        ph = ph or self.phrases[self.idx]
        return self.store.entry(ph.unit, ph.fname)

    def _active_takes(self, e: dict) -> list[dict]:
        return [t for t in e["takes"] if not t.get("deleted")]

    def _refresh_list(self) -> None:
        self.lst.delete(0, tk.END)
        for i, ph in enumerate(self.phrases):
            e = self._entry(ph)
            n = len(self._active_takes(e))
            mark = "✅" if e["approved"] else "⬜"
            label = ph.ru if not ph.no_speech else "(у референсі немає мови)"
            self.lst.insert(tk.END, f"{mark} {label}" + (f"   · {n}" if n else ""))
            self.lst.itemconfig(i, fg=GREEN if e["approved"] else ("#999" if ph.no_speech else "black"))
        self.lst.selection_clear(0, tk.END)
        if self.phrases:
            self.lst.selection_set(self.idx)
            self.lst.see(self.idx)
        done, total = self._unit_progress(self.unit)
        all_done = sum(self._unit_progress(u)[0] for u, _ in self.units)
        all_total = sum(self._unit_progress(u)[1] for u, _ in self.units)
        self.lbl_progress.config(text=f"Затверджено: {done}/{total}   ·   вся Орда: {all_done}/{all_total}")
        cur = self.cmb_unit.current()
        self.cmb_unit["values"] = [self._unit_label(u, t) for u, t in self.units]
        if cur >= 0:
            self.cmb_unit.current(cur)

    def _on_list_select(self, _e=None) -> None:
        sel = self.lst.curselection()
        if not sel:
            return
        if self.recording:  # під час запису не перемикаємось — повертаємо виділення
            self.lst.selection_clear(0, tk.END)
            self.lst.selection_set(self.idx)
            return
        if sel[0] != self.idx:
            self._select(sel[0])

    def _step(self, d: int) -> None:
        if self.recording or not self.phrases:
            return
        self._select(max(0, min(len(self.phrases) - 1, self.idx + d)))

    def _next_unapproved(self) -> None:
        if self.recording:
            return
        n = len(self.phrases)
        for k in range(1, n + 1):
            j = (self.idx + k) % n
            if not self._entry(self.phrases[j])["approved"] and not self.phrases[j].no_speech:
                self._select(j)
                return
        messagebox.showinfo("Готово", "Усі репліки цього юніта затверджено 🎉")

    def _select(self, idx: int) -> None:
        if not self.phrases:
            return
        self._save_text()
        self._stop_play()
        self.idx = idx
        self.lst.selection_clear(0, tk.END)
        self.lst.selection_set(idx)
        self.lst.see(idx)
        self._render_phrase()

    # ================================================================ картка репліки
    def _render_phrase(self) -> None:
        ph = self.phrases[self.idx]
        e = self._entry(ph)
        kind = TYPE_UA[ph.ptype]
        extra = "  ·  ⚠ у референсі немає мови (вирізана вотермарка)" if ph.no_speech else ""
        self.lbl_meta.config(text=f"Репліка {self.idx + 1} з {len(self.phrases)}  ·  {kind}  ·  "
                                  f"{ph.fname}  ·  оригінал {ph.ru_dur:.2f} с{extra}")
        self.lbl_ru.config(text=f"«{ph.ru}»")
        self._reset_text_field()
        self.lbl_direction.config(text=f"Як озвучувати (voice bible): {ph.direction}" if ph.direction else "")
        self._render_approval()
        self._render_takes()
        self._render_history()

    def _reset_text_field(self) -> None:
        ph = self.phrases[self.idx]
        e = self._entry(ph)
        self.var_ua.set(e["ua_text"] if e["ua_text"] is not None else ph.ua_hint)
        self.text_owner = ph
        self.lbl_text_saved.config(text="✎ ваш текст" if e["ua_text"] is not None else
                                   ("пропозиція" if ph.ua_hint else "введіть текст"))

    def _save_text(self) -> None:
        ph = self.text_owner
        if ph is None:
            return
        e = self._entry(ph)
        new = self.var_ua.get().strip()
        cur = e["ua_text"] if e["ua_text"] is not None else ph.ua_hint
        if new == cur:
            return
        e["ua_text"] = new
        self.store.log(ph.unit, ph.fname, f"текст змінено: «{cur}» → «{new}»")
        self.store.save()
        self.lbl_text_saved.config(text="✔ збережено")
        self._render_history()

    def _render_approval(self) -> None:
        e = self._entry()
        self.btn_unapprove.pack_forget()
        self.btn_play_game.pack_forget()
        if e["approved"]:
            t = next((t for t in e["takes"] if t["file"] == e["approved"]), None)
            label = f"Спроба {take_no(e['approved'])}" if t else e["approved"]
            self.appr_box.config(bg=GREEN_BG)
            self.lbl_appr.config(text=f"✅ ЗАТВЕРДЖЕНО: {label}  →  game-files/Units/{RACE}/{self.unit}/"
                                      f"{self.phrases[self.idx].fname}", bg=GREEN_BG, fg=GREEN)
            self.btn_play_game.pack(side="right")
            self.btn_unapprove.pack(side="right", padx=6)
        else:
            self.appr_box.config(bg="#fff1e0")
            self.lbl_appr.config(text="⬜ Ще не затверджено — запишіть спробу і натисніть «Затвердити»",
                                 bg="#fff1e0", fg=ORANGE)

    def _render_takes(self) -> None:
        self.takes.clear()
        ph = self.phrases[self.idx]
        e = self._entry(ph)
        active = self._active_takes(e)
        deleted = [t for t in e["takes"] if t.get("deleted")]
        self.lbl_takes_hdr.config(text=f"Спроби ({len(active)})")
        self.btn_toggle_deleted.config(
            text=(f"Сховати видалені ({len(deleted)})" if self.show_deleted else f"Показати видалені ({len(deleted)})"),
            state="normal" if deleted else "disabled")
        if not active:
            ttk.Label(self.takes.inner, text="— ще немає спроб. Послухайте оригінал і натисніть «Записати спробу» "
                                             "(або Пробіл).", foreground=GREY).pack(anchor="w", pady=6)
        for t in reversed(active):  # найновіша зверху
            self._take_row(ph, e, t, deleted=False)
        if self.show_deleted and deleted:
            ttk.Label(self.takes.inner, text="Видалені спроби (лежать у _deleted/, можна відновити):",
                      foreground=GREY).pack(anchor="w", pady=(12, 2))
            for t in reversed(deleted):
                self._take_row(ph, e, t, deleted=True)

    def _take_path(self, unit: str, t: dict) -> Path:
        d = TAKES_ROOT / unit
        return (d / "_deleted" / t["file"]) if t.get("deleted") else (d / t["file"])

    def _take_row(self, ph: Phrase, e: dict, t: dict, deleted: bool) -> None:
        approved = e["approved"] == t["file"] and not deleted
        bg = GREEN_BG if approved else ("#f2f2f2" if deleted else self.cget("background"))
        row = tk.Frame(self.takes.inner, bg=bg, padx=8, pady=4)
        row.pack(fill="x", pady=2)
        path = self._take_path(ph.unit, t)
        exists = path.exists()
        d = duration(path) if exists else 0.0
        diff = d - ph.ru_dur
        n = take_no(t["file"])
        txt = f"Спроба {n}" if n else t["file"]
        if exists:
            txt += f"   {d:.2f} с"
        else:
            txt += "   (файл відсутній!)"
        tk.Label(row, text=txt, bg=bg, font=("SF Pro Text", 13, "bold" if approved else "normal"),
                 fg=GREY if deleted else "black", width=17, anchor="w").pack(side="left")
        if exists and ph.ru_dur > 0:
            col = RED if diff > ph.ru_dur * 0.15 + 0.15 else GREY
            tk.Label(row, text=f"{diff:+.2f} с до оригіналу", bg=bg, fg=col, width=17, anchor="w").pack(side="left")
        tk.Label(row, text=short_time(t.get("deleted") if deleted else t.get("created")), bg=bg, fg=GREY,
                 width=11, anchor="w").pack(side="left")
        st = "normal" if exists else "disabled"
        ttk.Button(row, text="▶ Слухати", takefocus=False, state=st,
                   command=lambda p=path: self._play([p])).pack(side="left", padx=3)
        ttk.Button(row, text="▶ Оригінал → спроба", takefocus=False, state=st,
                   command=lambda p=path: self._play([ph.ref_path, p])).pack(side="left", padx=3)
        if deleted:
            ttk.Button(row, text="↩ Відновити", takefocus=False, state=st,
                       command=lambda tt=t: self._restore(tt)).pack(side="left", padx=3)
            return
        if approved:
            tk.Label(row, text="✅ ЗАТВЕРДЖЕНО", bg=bg, fg=GREEN,
                     font=("SF Pro Text", 13, "bold")).pack(side="left", padx=8)
        else:
            ttk.Button(row, text="✔ Затвердити", takefocus=False, state=st,
                       command=lambda tt=t: self._approve(tt)).pack(side="left", padx=3)
        ttk.Button(row, text="🗑 Видалити", takefocus=False,
                   command=lambda tt=t: self._delete(tt)).pack(side="right", padx=3)

    def _render_history(self) -> None:
        e = self._entry()
        self.txt_hist.config(state="normal")
        self.txt_hist.delete("1.0", tk.END)
        lines = [f"{short_time(h['ts']):>11}  {h['action']}" for h in e["history"][-30:]]
        self.txt_hist.insert("1.0", "\n".join(reversed(lines)) or "—")
        self.txt_hist.config(state="disabled")

    def _toggle_deleted(self) -> None:
        self.show_deleted = not self.show_deleted
        self._render_takes()

    def _refresh_all(self) -> None:
        self._refresh_list()
        self._render_approval()
        self._render_takes()
        self._render_history()

    # ================================================================ дії зі спробами
    def _approve(self, t: dict) -> None:
        ph = self.phrases[self.idx]
        e = self._entry(ph)
        src = self._take_path(ph.unit, t)
        if not src.exists():
            messagebox.showerror("Немає файлу", f"Файл спроби не знайдено:\n{src}")
            return
        dst = ph.game_path
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not (self.var_trim.get() and self._export_trimmed(src, dst)):
            shutil.copy2(src, dst)
        prev = e["approved"]
        e["approved"] = t["file"]
        self.store.log(ph.unit, ph.fname, (f"затверджено спробу {take_no(t['file'])}"
                                           + (f" (замість спроби {take_no(prev)})" if prev else "")))
        self.store.save()
        self._refresh_all()

    def _export_trimmed(self, src: Path, dst: Path) -> bool:
        """Копія для гри: обрізати тишу на початку/в кінці, формат 22050 Hz mono s16."""
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

    def _unapprove(self) -> None:
        ph = self.phrases[self.idx]
        e = self._entry(ph)
        if not e["approved"]:
            return
        if not messagebox.askyesno("Скасувати затвердження?",
                                   f"Спроба {take_no(e['approved'])} лишиться у списку спроб, "
                                   f"а файл для гри\n{ph.fname} буде прибрано.\n\nСкасувати затвердження?"):
            return
        self._drop_approval(ph, e, reason="затвердження скасовано")
        self.store.save()
        self._refresh_all()

    def _drop_approval(self, ph: Phrase, e: dict, reason: str) -> None:
        prev = e["approved"]
        e["approved"] = None
        ph.game_path.unlink(missing_ok=True)
        self.store.log(ph.unit, ph.fname, f"{reason} (спроба {take_no(prev)})")

    def _delete(self, t: dict) -> None:
        ph = self.phrases[self.idx]
        e = self._entry(ph)
        n = take_no(t["file"])
        is_appr = e["approved"] == t["file"]
        msg = f"Видалити спробу {n}?\n\nФайл переїде в _deleted/ — його можна буде відновити."
        if is_appr:
            msg += "\n\n⚠ Це ЗАТВЕРДЖЕНА спроба: затвердження буде знято, файл для гри прибрано."
        if not messagebox.askyesno("Видалити спробу?", msg, icon="warning"):
            return
        self._stop_play()
        if is_appr:
            self._drop_approval(ph, e, reason="затвердження знято через видалення")
        src = self._take_path(ph.unit, t)
        ddir = TAKES_ROOT / ph.unit / "_deleted"
        ddir.mkdir(parents=True, exist_ok=True)
        if src.exists():
            shutil.move(str(src), str(ddir / t["file"]))
        t["deleted"] = now()
        self.store.log(ph.unit, ph.fname, f"видалено спробу {n}")
        self.store.save()
        self._refresh_all()

    def _restore(self, t: dict) -> None:
        ph = self.phrases[self.idx]
        src = self._take_path(ph.unit, t)
        dst = TAKES_ROOT / ph.unit / t["file"]
        if dst.exists():
            messagebox.showerror("Конфлікт", f"Файл {dst.name} уже існує серед активних спроб.")
            return
        if src.exists():
            shutil.move(str(src), str(dst))
        t["deleted"] = None
        self.store.log(ph.unit, ph.fname, f"відновлено спробу {take_no(t['file'])}")
        self.store.save()
        self._refresh_all()

    # ================================================================ програвання
    def _play(self, paths: list[Path]) -> None:
        self._stop_play()
        self.play_queue = [p for p in paths if p.exists()]
        self._play_next()

    def _play_next(self) -> None:
        if not self.play_queue:
            return
        p = self.play_queue.pop(0)
        self.play_proc = subprocess.Popen(["afplay", str(p)])
        self.after(80, self._poll_play, self.play_proc)

    def _poll_play(self, proc: subprocess.Popen) -> None:
        if proc is not self.play_proc:
            return  # програвання вже замінене іншим
        if proc.poll() is None:
            self.after(80, self._poll_play, proc)
        elif self.play_queue:
            self.after(250, self._play_next)  # коротка пауза між оригіналом і спробою

    def _stop_play(self) -> None:
        self.play_queue = []
        if self.play_proc and self.play_proc.poll() is None:
            self.play_proc.terminate()
        self.play_proc = None

    def _play_ref(self) -> None:
        if self.phrases:
            self._play([self.phrases[self.idx].ref_path])

    def _play_last_take(self) -> None:
        if not self.phrases:
            return
        act = self._active_takes(self._entry())
        if act:
            self._play([self._take_path(self.unit, act[-1])])

    def _play_game_file(self) -> None:
        self._play([self.phrases[self.idx].game_path])

    # ================================================================ запис
    def _toggle_record(self) -> None:
        if self.recording:
            self._stop_record()
        else:
            self._start_record()

    def _next_take_file(self, ph: Phrase) -> Path:
        tdir = TAKES_ROOT / ph.unit
        used = [take_no(t["file"]) for t in self._entry(ph)["takes"]]
        for d in (tdir, tdir / "_deleted"):
            if d.is_dir():
                used += [take_no(f.name) for f in d.glob(f"{ph.stem}.take*.wav")]
        n = max(used, default=0) + 1
        while (tdir / f"{ph.stem}.take{n}.wav").exists() or (tdir / "_deleted" / f"{ph.stem}.take{n}.wav").exists():
            n += 1
        return tdir / f"{ph.stem}.take{n}.wav"

    def _start_record(self) -> None:
        if not self.phrases or self.recording:
            return
        if not shutil.which("ffmpeg"):
            messagebox.showerror("Немає ffmpeg", "Встановіть ffmpeg:  brew install ffmpeg")
            return
        self._save_text()
        self._stop_play()
        ph = self.phrases[self.idx]
        target = self._next_take_file(ph)
        target.parent.mkdir(parents=True, exist_ok=True)
        self.rec_log = tempfile.TemporaryFile()
        try:
            self.rec_proc = subprocess.Popen(
                ["ffmpeg", "-hide_banner", "-nostats", "-loglevel", "error", "-y",
                 "-f", "avfoundation", "-i", MIC, "-ar", str(SR), "-ac", "1", "-sample_fmt", "s16",
                 str(target)],
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=self.rec_log)
        except OSError as ex:
            messagebox.showerror("Запис не стартував", str(ex))
            return
        self.rec_ctx = (ph, target)
        self.rec_t0 = time.monotonic()
        self.recording = True
        self.btn_rec.config(text="■  ЗУПИНИТИ  (Пробіл)")
        self.cmb_unit.config(state="disabled")
        self.lbl_rec.config(text="⏳ вмикаю мікрофон…", fg=ORANGE)
        self.after(100, self._rec_tick)

    def _rec_tick(self) -> None:
        if not self.recording:
            return
        ph, target = self.rec_ctx
        el = time.monotonic() - self.rec_t0
        if self.rec_proc.poll() is not None:  # ffmpeg завершився сам — помилка
            self._finish_record()
            return
        live = target.exists() and target.stat().st_size > 2000
        if live:
            self.lbl_rec.config(text=f"🔴 ГОВОРІТЬ!   {el:4.1f} с", fg=RED)
        if el >= MAX_REC_SEC:
            self._stop_record()
            return
        self.after(100, self._rec_tick)

    def _stop_record(self) -> None:
        if not (self.recording and self.rec_proc):
            return
        p = self.rec_proc
        try:
            p.stdin.write(b"q")
            p.stdin.flush()
            p.stdin.close()
        except Exception:
            pass
        try:
            p.wait(timeout=4)
        except subprocess.TimeoutExpired:
            p.terminate()
            try:
                p.wait(timeout=2)
            except subprocess.TimeoutExpired:
                p.kill()
        self._finish_record()

    def _finish_record(self) -> None:
        ph, target = self.rec_ctx
        self.recording = False
        self.rec_proc = None
        self.btn_rec.config(text="●  Записати спробу  (Пробіл)")
        self.cmb_unit.config(state="readonly")
        self.lbl_rec.config(text="")
        err = ""
        if self.rec_log:
            self.rec_log.seek(0)
            err = self.rec_log.read().decode("utf-8", "replace").strip()[-600:]
            self.rec_log.close()
            self.rec_log = None
        d = duration(target) if target.exists() else 0.0
        if d < MIN_TAKE_SEC:
            target.unlink(missing_ok=True)
            messagebox.showerror(
                "Запис не вдався",
                "Файл порожній або занадто короткий.\n\n"
                "Якщо це перший запис — дозвольте доступ до мікрофона:\n"
                "Системні параметри → Конфіденційність і безпека → Мікрофон → увімкніть Terminal "
                "(або програму, з якої запущено студію), потім перезапустіть студію."
                + (f"\n\nffmpeg: {err}" if err else ""))
            return
        e = self._entry(ph)
        e["takes"].append({"file": target.name, "created": now(), "deleted": None})
        self.store.log(ph.unit, ph.fname, f"записано спробу {take_no(target.name)} ({d:.2f} с)")
        self.store.save()
        if self.phrases and self.phrases[self.idx] is ph:
            self._refresh_all()
        else:
            self._refresh_list()
        if self.var_autoplay.get():
            self._play([target])

    # ================================================================ інше
    def _open_game_dir(self) -> None:
        d = GAME_ROOT / self.unit
        d.mkdir(parents=True, exist_ok=True)
        subprocess.run(["open", str(d)], check=False)

    def _on_close(self) -> None:
        if self.recording:
            self._stop_record()
        self._save_text()
        self._stop_play()
        self.store.save()
        self.destroy()


if __name__ == "__main__":
    Studio().mainloop()
