"""Параметри генерації однієї репліки: перевірені, серіалізуються в JSON, зберігаються в побічному json кожного варіанта.

  text_override  текст для моделі (за замовчуванням — текст репліки): наголоси (U+0301), «…», «!!!», теги [..]
  style          тег стилю/емоції Fish S2-Pro: `[whisper]`, `[excited]`… — вільна англійська фраза в дужках
                 (ПЕРЕВІРЕНО за документацією fishaudio/fish-speech: «inline natural-language instructions»,
                 приклади [pause] [excited] [whisper] [angry] [laughing]); перелік у STYLE_PRESETS — лише підказки
  ref_takes      власні затверджені дублі для референсу голосу (None = автовибір); валідує refs.py
  variability    «Варіативність» 0..1 → temperature/top_p у безпечних межах (схема Fish: 0.1..1.0)
  seed           None = випадковий (призначається при постановці в чергу)
  n              кількість варіантів 1..MAX_N (seed, seed+1, …)
  engine         назва двигуна з реєстру engines/
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass

MAX_N = 8
MAX_TEXT = 400
MAX_REFS = 5
SEED_MAX = 2**31 - 1
TEMP_RANGE = (0.5, 0.9)      # variability 0 → 0.5 (стабільно), 1 → 0.9 (живо, ризик збоїв)
TOP_P_RANGE = (0.6, 0.9)
DEFAULT_ENGINE = "fish-s2-pro"
FIELDS = ("text_override", "style", "ref_takes", "variability", "seed", "n", "engine")
TAG_RE = re.compile(r"\[([^\[\]]*)\]")
STYLE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9 '\-]{0,39}$")
# Підказки для UI. Перші п'ять — з документації Fish S2-Pro; решту власник уже пробував у пілоті (aigen.STYLE_TAGS).
STYLE_PRESETS = [
    {"tag": "whisper", "uk": "пошепки", "verified": "docs"}, {"tag": "angry", "uk": "злісно", "verified": "docs"},
    {"tag": "laughing", "uk": "сміючись", "verified": "docs"}, {"tag": "excited", "uk": "збуджено", "verified": "docs"},
    {"tag": "pause", "uk": "пауза", "verified": "docs"},
    {"tag": "hurried", "uk": "квапливо", "verified": "pilot"}, {"tag": "cheerful", "uk": "бадьоро", "verified": "pilot"},
    {"tag": "sighing", "uk": "зітхаючи", "verified": "pilot"}, {"tag": "indignant", "uk": "обурено", "verified": "pilot"},
    {"tag": "proud", "uk": "гордо", "verified": "pilot"}, {"tag": "playful", "uk": "грайливо", "verified": "pilot"},
]


class ParamsError(ValueError):
    """Некоректні параметри генерації (повідомлення показується користувачеві)."""


def sampling(variability: float) -> tuple[float, float]:
    """«Варіативність» 0..1 → (temperature, top_p)."""
    v = max(0.0, min(1.0, float(variability)))
    return (round(TEMP_RANGE[0] + (TEMP_RANGE[1] - TEMP_RANGE[0]) * v, 3),
            round(TOP_P_RANGE[0] + (TOP_P_RANGE[1] - TOP_P_RANGE[0]) * v, 3))


def check_tags(text: str) -> None:
    rest = TAG_RE.sub("", text)
    if "[" in rest or "]" in rest:
        raise ParamsError("квадратні дужки лише парами й без вкладення: [whisper]")
    for m in TAG_RE.finditer(text):
        if not STYLE_RE.match(m.group(1).strip()):
            raise ParamsError(f"тег [{m.group(1)}]: англійська фраза до 40 символів (літери, пробіл, дефіс)")


def strip_tags(text: str) -> str:
    return " ".join(TAG_RE.sub(" ", text).split())


@dataclass(frozen=True)
class GenParams:
    text_override: str | None = None
    style: str | None = None
    ref_takes: tuple[str, ...] | None = None
    variability: float = 0.5
    seed: int | None = None
    n: int = 1
    engine: str = DEFAULT_ENGINE

    def __post_init__(self) -> None:
        t = self.text_override
        if t is not None:
            if not isinstance(t, str) or not t.strip():
                raise ParamsError("text_override: непорожній рядок або null")
            if len(t) > MAX_TEXT:
                raise ParamsError(f"text_override: до {MAX_TEXT} символів")
            check_tags(t)
        s = self.style
        if s is not None and (not isinstance(s, str) or not STYLE_RE.match(s)):
            raise ParamsError("style: англійська фраза до 40 символів без дужок, напр. whisper")
        r = self.ref_takes
        if r is not None:
            if (not isinstance(r, tuple) or not 1 <= len(r) <= MAX_REFS or len(set(r)) != len(r)
                    or not all(isinstance(x, str) and x for x in r)):
                raise ParamsError(f"ref_takes: 1..{MAX_REFS} унікальних імен дублів або null (автовибір)")
        v = self.variability
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 1:
            raise ParamsError("variability: число 0..1")
        sd = self.seed
        if sd is not None and (isinstance(sd, bool) or not isinstance(sd, int) or not 0 <= sd <= SEED_MAX):
            raise ParamsError(f"seed: ціле 0..{SEED_MAX} або null")
        n = self.n
        if isinstance(n, bool) or not isinstance(n, int) or not 1 <= n <= MAX_N:
            raise ParamsError(f"n: ціле 1..{MAX_N}")
        if not isinstance(self.engine, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,40}", self.engine):
            raise ParamsError("engine: назва двигуна (a-z, 0-9, «-»)")

    # ---- серіалізація
    def to_dict(self) -> dict:
        d = asdict(self)
        d["ref_takes"] = list(self.ref_takes) if self.ref_takes is not None else None
        return d

    @classmethod
    def from_dict(cls, d: dict | None) -> GenParams:
        if d is not None and not isinstance(d, dict):
            raise ParamsError("параметри мають бути об'єктом")
        d = dict(d or {})
        unknown = set(d) - set(FIELDS)
        if unknown:
            raise ParamsError("невідомі параметри: " + ", ".join(sorted(unknown)))
        if isinstance(d.get("ref_takes"), list):
            d["ref_takes"] = tuple(d["ref_takes"])
        return cls(**d)

    # ---- похідні
    def with_seed(self, seed: int | None) -> GenParams:
        return GenParams(**{**{k: getattr(self, k) for k in FIELDS}, "seed": seed})

    def seeds(self, base: int) -> list[int]:
        return [(base + i) % (SEED_MAX + 1) for i in range(self.n)]

    def sampling(self) -> tuple[float, float]:
        return sampling(self.variability)

    def text_for(self, line_text: str) -> str:
        """Текст, що йде в модель: override або текст репліки; style додає тег спереду, якщо в тексті його ще немає."""
        base = (self.text_override if self.text_override is not None else line_text).strip()
        return f"[{self.style}] {base}" if self.style and not base.startswith("[") else base

    def plain_for(self, line_text: str) -> str:
        """Цільовий текст без тегів — для CER."""
        return strip_tags(self.text_override if self.text_override is not None else line_text)


def schema() -> dict:
    """Опис для UI: межі й підказки (форма не вгадує їх сама)."""
    return {"max_n": MAX_N, "max_text": MAX_TEXT, "max_refs": MAX_REFS, "variability": {"min": 0, "max": 1, "default": 0.5,
            "temperature_range": list(TEMP_RANGE), "top_p_range": list(TOP_P_RANGE)},
            "style_presets": STYLE_PRESETS, "defaults": GenParams().to_dict()}
