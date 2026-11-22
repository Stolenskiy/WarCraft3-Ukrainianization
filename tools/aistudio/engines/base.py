"""Контракт двигуна ШІ-голосу (локального чи хмарного). Двигун = один файл `engines/<ім'я>.py` з класом-нащадком Engine.

Вимоги до будь-якого двигуна:
  * `info` — метадані (ліцензія, чи комерційний, мови, які параметри розуміє, вартість, вимоги);
  * `status()` — готовність: ready | missing_model | missing_key | missing_env (без важких імпортів і мережі);
  * `map_params()` — перетворення наших параметрів у власні; непідтримувані ПОВЕРТАЄ списком, не губить мовчки;
  * `generate()` — сирі wav (формат нормалізує конвеєр), результат мусить мати ту саму метадані (engine, license), що й локальні;
  * хмарні двигуни (`kind == "cloud"`): ключ лише з env/data/local/settings.json (config.api_key), явна згода на
    вивантаження власних дублів стороннім (config.upload_consent) — перевіряє `check_ready()`; попередження про вартість/ліміти
    віддає `warnings()`.
Ліцензія вихідних ШІ-реплік у пакетах = `info.output_license` (невідомо → CC BY-NC 4.0, див. ADR 0007).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from .. import config

NC_LICENSE = "CC BY-NC 4.0"
KNOWN_OUTPUT_LICENSES = ("CC BY-NC 4.0", "CC BY 4.0")
PARAMS = ("text_override", "style", "ref_takes", "variability", "seed")


class EngineError(Exception):
    """Збій двигуна (повідомлення — користувачеві)."""


class Cancelled(EngineError):
    """Генерацію скасовано (процес двигуна зупинено)."""


@dataclass(frozen=True)
class EngineInfo:
    name: str
    title: str
    kind: str                          # "local" | "cloud"
    license: str                       # ліцензія моделі/сервісу
    license_url: str
    commercial: bool                   # чи дозволене комерційне використання результату за ліцензією двигуна
    languages: tuple[str, ...] = ("uk",)
    supports: tuple[str, ...] = ()     # підмножина PARAMS
    cost_note: str = ""
    requirements: tuple[str, ...] = ()  # людською: «GPU/MPS», «ключ API», «10 ГБ диска»
    output_license: str = NC_LICENSE   # ліцензія ШІ-реплік у пакетах голосів; невідома → NC

    def __post_init__(self) -> None:
        if self.kind not in ("local", "cloud"):
            raise ValueError(f"engine.kind: local|cloud, не {self.kind!r}")
        bad = set(self.supports) - set(PARAMS)
        if bad:
            raise ValueError(f"engine.supports: невідомі параметри {sorted(bad)}")
        if self.output_license not in KNOWN_OUTPUT_LICENSES:
            object.__setattr__(self, "output_license", NC_LICENSE)       # невідомо → найсуворіше

    @property
    def cloud(self) -> bool:
        return self.kind == "cloud"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["languages"], d["supports"], d["requirements"] = list(self.languages), list(self.supports), list(self.requirements)
        return d


class Engine:
    info: EngineInfo

    # ---- готовність
    def status(self) -> dict:
        """{state: ready|missing_model|missing_key|missing_env, detail: str}."""
        raise NotImplementedError

    def warnings(self) -> list[str]:
        """Вартість, ліміти, приватність — показуються перед генерацією."""
        return []

    def check_ready(self) -> None:
        st = self.status()
        if st["state"] != "ready":
            raise EngineError(f"двигун {self.info.name} не готовий: {st['state']} — {st.get('detail', '')}")
        if self.info.cloud and not config.upload_consent(self.info.name):
            raise config.ConsentError(
                f"{self.info.title}: ваші дублі (референс голосу) буде ВИВАНТАЖЕНО стороннім сервісом; потрібна окрема згода "
                f"(ai-consent --engine {self.info.name} --accept)")

    # ---- параметри
    def map_params(self, p) -> tuple[dict, list[str]]:
        """GenParams → (параметри, що двигун розуміє, непідтримувані назви). Непідтримувані, яких користувач
        торкнувся (не значення за замовчуванням), ПОВЕРТАЮТЬСЯ — їх показують у UI, а не гублять мовчки."""
        given = {"text_override": p.text_override, "style": p.style, "ref_takes": p.ref_takes, "seed": p.seed,
                 "variability": p.variability}
        sup = set(self.info.supports)
        unsupported = [k for k, v in given.items() if k not in sup and v not in (None, 0.5)]
        return {k: v for k, v in given.items() if k in sup}, unsupported

    # ---- робота
    def generate(self, jobs: list, raws: dict, log) -> None:
        """jobs — aigen.Job (text, seed, temperature, top_p, refs, max_new); raws[i] — куди писати сирий wav."""
        raise NotImplementedError

    def similarity(self, pairs: list[dict]) -> dict[str, float]:
        return {}

    def cancel(self) -> None:
        """Зупиняє поточну генерацію (убиває підпроцес / обриває запит)."""
