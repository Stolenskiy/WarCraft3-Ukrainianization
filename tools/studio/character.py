"""Пресет персонажа: висота, форманти, «гроул», простір — щоб один голос звучав як різні персонажі раси.

Пресет {enabled, pitch_st, formant_pct, drive, reverb, tail_s} живе в стані каталогу (data/studio/<cid>.json →
"characters": {gid: preset}); немає запису → пропозиція з voice bible (`suggest`), ВИМКНЕНА, тож старий стан і
файли гри не змінюються, доки користувач не ввімкне пресет. EQ персонажа — наявний профіль групи (eq.py).

ffmpeg, лише вбудовані фільтри (rubberband не потрібен):
  висота   — aresample → asetrate=SR·r → aresample → atempo=1/r: тривалість та сама, тон ×r;
  форманти — afftfilt: огинаюча спектра (ковзне середнє |X| по 2·K+1 бінах) розтягується в f/r раз, гармоніки
             лишаються на місці — тож «висота» сама тембр не «мультяшить», а «форманти» міняють тембр без зміни тону;
  гроул    — volume↑ → asoftclip=tanh → volume↓ (сатурація) + tremolo 30 Гц (шорсткість гарчання);
  простір  — два aecho: ранні відбиття 13–37 мс і хвіст до tail_s.
Місце в ланцюжку експорту (svc/export.py): … темп → висота/форманти → EQ → гроул → простір → гучність.
"""
from __future__ import annotations

import math
import re
from pathlib import Path

SR = 22050
LIMITS = {"pitch_st": (-6.0, 6.0), "formant_pct": (-20.0, 20.0), "drive": (0.0, 100.0),
          "reverb": (0.0, 100.0), "tail_s": (0.1, 2.0)}
DEFAULT = {"enabled": False, "pitch_st": 0.0, "formant_pct": 0.0, "drive": 0.0, "reverb": 0.0, "tail_s": 0.4}
FFT_WIN, ENV_K = 1024, 5        # 21.5 Гц на бін; огинаюча по 11 бінах (≈ 240 Гц) згладжує гармоніки голосу
MAX_ENV_GAIN = 4                # не підсилювати бін більше ніж на +12 дБ (шум у «дірах» спектра)

# Расові палітри (docs/voice-bible/README.md): база, до якої додаються відхилення з аркуша юніта.
RACE_BASE = {
    "orc": ({"pitch_st": -1.0, "formant_pct": -10.0, "drive": 15.0, "reverb": 0.0, "tail_s": 0.3},
            "раса: нижче, форманти −10 %, грудна вага, сухо"),
    "undead": ({"pitch_st": 0.0, "formant_pct": 0.0, "drive": 10.0, "reverb": 35.0, "tail_s": 1.0},
               "раса: холодний склеп — довгий хвіст"),
    "nightelf": ({"pitch_st": 0.0, "formant_pct": 5.0, "drive": 0.0, "reverb": 20.0, "tail_s": 0.6},
                 "раса: нічний ліс — яскраві форманти, лісовий хвіст"),
    "human": ({"pitch_st": 0.0, "formant_pct": 0.0, "drive": 0.0, "reverb": 10.0, "tail_s": 0.3},
              "раса: сухо, коротке раннє відображення"),
}
GRIT = re.compile(r"хрип|гуркіт|\bрик|\bрев(?!ер)|гроул|подвійн|subharmonic|клекот|деренч|гарчан|грубий")
_PITCH = re.compile(r"pitch(?:-up)?\s*\(?\s*[×x]?\s*(\d+[.,]\d+)(?:\s*[–/-]\s*(\d+[.,]\d+))?", re.I)
_FORMANT = re.compile(r"formant\s*([−+-])\s*(\d+)\s*%", re.I)
_DRY = re.compile(r"\bсух[оиі]\b|сухий|найсухіш|без ревер|без хвоста|хвіст\s*\*?сух")
_WET = re.compile(r"хвіст|хвоста|відображен|відгомін|відлун|\bлуна\b|\bлун\b|простір|ревер")


class CharacterError(Exception):
    """Некоректний пресет персонажа (показується користувачеві)."""


def validate(p) -> dict:
    """Перевірити й нормалізувати пресет (повертає чисту копію; відсутні поля — типові)."""
    if not isinstance(p, dict):
        raise CharacterError("пресет персонажа має бути об'єктом")
    out = {"enabled": bool(p.get("enabled", DEFAULT["enabled"]))}
    for k, (lo, hi) in LIMITS.items():
        v = p.get(k, DEFAULT[k])
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v:
            raise CharacterError(f"{k}: очікується число")
        if not lo <= v <= hi:
            raise CharacterError(f"{k}: {v} поза межами {lo:g}…{hi:g}")
        out[k] = round(float(v), 2)
    return out


def _env(at: str) -> str:
    """Огинаюча в біні `at`: сума |X| по сусідніх бінах (real/imag поза межами ffmpeg обрізає до країв)."""
    return "+".join(f"hypot(real({at}{k:+d},ch),imag({at}{k:+d},ch))" for k in range(-ENV_K, ENV_K + 1))


def formant_filter(ratio: float) -> str:
    """afftfilt, що зсуває огинаючу спектра в `ratio` раз (форманти), не чіпаючи гармонік (висоти)."""
    g = f"min({MAX_ENV_GAIN},({_env(f'floor(b/{ratio:.4f})')})/(({_env('b')})+1e-9))"
    return f"afftfilt=real='re*{g}':imag='im*{g}':win_size={FFT_WIN}:overlap=0.75"


def to_ffmpeg(p: dict) -> tuple[list[str], list[str]]:
    """Пресет → (голос: висота/форманти — ДО EQ, ефекти: гроул/простір — ПІСЛЯ EQ). Вимкнений → ([], [])."""
    if not p.get("enabled"):
        return [], []
    voice, fx = [], []
    r = 1.0
    if abs(p["pitch_st"]) >= 0.05:
        rate = round(SR * 2 ** (p["pitch_st"] / 12))
        r = rate / SR
        voice += [f"aresample={SR}", f"asetrate={rate}", f"aresample={SR}", f"atempo={1 / r:.5f}"]
    ratio = (1 + p["formant_pct"] / 100) / r      # asetrate зсунув і форманти — повертаємо їх і додаємо свій зсув
    if abs(ratio - 1) > 0.004:
        voice.append(formant_filter(ratio))
    if p["drive"] > 0:
        pre = round(p["drive"] / 100 * 18, 1)
        fx += [f"volume={pre:g}dB", "asoftclip=type=tanh", f"volume={-pre:g}dB",
               f"tremolo=f=30:d={min(0.5, p['drive'] / 100 * 0.4):.2f}"]
    if p["reverb"] > 0:
        a, t = p["reverb"] / 100, p["tail_s"] * 1000
        early = "|".join(f"{a * d:.3f}" for d in (0.45, 0.38, 0.32, 0.26))
        tail = "|".join(f"{a * d:.3f}" for d in (0.4, 0.3, 0.22, 0.15))
        fx += [f"aecho=0.9:0.9:13|19|29|37:{early}",
               "aecho=0.9:0.9:" + "|".join(f"{max(1, round(t * k))}" for k in (0.11, 0.19, 0.29, 0.41)) + f":{tail}"]
    return voice, fx


# ---------------------------------------------------------------- пропозиція з voice bible
_bible_cache: dict[tuple[str, int], dict] = {}


def bible_processing(path: Path) -> dict[str, dict]:
    """docs/voice-bible/<race>.md → {unit: {"proc": текст «Обробка…», "timbre": текст «Тембр»}} (кеш за mtime)."""
    try:
        key = (str(path), path.stat().st_mtime_ns)
    except OSError:
        return {}
    if key in _bible_cache:
        return _bible_cache[key]
    units: dict[str, dict] = {}
    cur, field = None, None
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^###\s+(\w+)\s+—", line)
        if m:
            cur, field = units.setdefault(m.group(1), {"proc": "", "timbre": ""}), None
            continue
        if line.startswith("## "):
            cur = field = None
            continue
        if cur is None:
            continue
        m = re.match(r"^\*\*(Обробка|Тембр)[^*]*:\*\*\s*(.*)", line)
        if m:
            field = "proc" if m.group(1) == "Обробка" else "timbre"
            cur[field] = m.group(2).strip()
        elif field and line.strip() and not line.startswith(("**", "|", "#")):
            cur[field] += " " + line.strip()
        else:
            field = None
    _bible_cache[key] = units
    return units


def _clamp(k: str, v: float) -> float:
    lo, hi = LIMITS[k]
    return round(max(lo, min(hi, v)), 1 if k in ("pitch_st", "tail_s") else 0)


def suggest(race: str | None, proc_text: str = "", timbre: str = "") -> tuple[dict, list[str]]:
    """Пропозиція пресета (вимкненого) з расової палітри й аркуша юніта + пояснення «чому так» (рядки для UI)."""
    base, race_why = RACE_BASE.get(race or "", (None, None))
    if base is None:
        return dict(DEFAULT), []
    p, why = {**DEFAULT, **base}, [race_why]
    proc, low = proc_text, f"{proc_text} {timbre}".lower()
    m = _PITCH.search(proc)
    if m:
        vals = [float(x.replace(",", ".")) for x in m.groups() if x]
        ratio = sum(vals) / len(vals)
        st = 12 * math.log2(ratio)
        p["pitch_st"] += st
        why.append(f"pitch ×{ratio:.2f} → {st:+.1f} пт")
    m = _FORMANT.search(proc)
    if m:
        p["formant_pct"] = float(m.group(2)) * (1 if m.group(1) == "+" else -1)
    elif re.search(r"яскрав\w*\s+формант", proc.lower()):
        p["formant_pct"] = max(p["formant_pct"], 5.0)
        why.append("яскраві форманти → +5 %")
    hits = sorted(set(GRIT.findall(low)))
    if hits:
        p["drive"] += 12 * len(hits)
        why.append(f"гроул: {', '.join(hits)}")
    pl = proc.lower()
    if _DRY.search(pl):
        p["reverb"] = 0.0
        why.append("сухо → без простору")
    elif _WET.search(pl):
        lvl = p["reverb"] or 15.0
        lvl *= 0.5 if re.search(r"дуже легк|ледь", pl) else 0.75 if "легк" in pl else 1
        if re.search(r"найдовш|дуже широк", pl):
            lvl, p["tail_s"] = lvl + 15, p["tail_s"] + 0.6
        elif re.search(r"довш|довг|широк|розтягн", pl):
            lvl, p["tail_s"] = lvl + 8, p["tail_s"] + 0.3
        if "корот" in pl:
            p["tail_s"] = max(0.2, p["tail_s"] - 0.3)
        p["reverb"] = lvl
        why.append(f"простір: {lvl:.0f} %, хвіст {p['tail_s']:.1f} с")
    return {"enabled": False, **{k: _clamp(k, p[k]) for k in LIMITS}}, why
