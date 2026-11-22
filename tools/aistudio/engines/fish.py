"""Fish Audio S2-Pro: локально (MPS/CUDA/CPU), клон ВЛАСНОГО голосу з власних дублів. Перший двигун.

Ліцензія — Fish Audio Research License (некомерційна): тому ШІ-репліки в пакетах голосів — CC BY-NC 4.0 (ADR 0007).
Параметри (ПЕРЕВІРЕНО: fish_speech/utils/schema.py ServeTTSRequest, fish_worker.py): text, references, seed,
temperature 0.1..1.0, top_p 0.1..1.0, max_new_tokens; інлайн-теги `[..]` — за документацією S2-Pro.
Робітник — tools/ai_engines/fish_worker.py у `.venv-fish` (окремий процес, пам'ять звільняється на виході).
"""
from __future__ import annotations

from pathlib import Path

from .. import config
from .base import Engine, EngineInfo
from .procrun import WorkerRunner

WORKERS = Path(__file__).resolve().parents[2] / "ai_engines"
NAME = "fish-s2-pro"


class FishEngine(Engine):
    info = EngineInfo(
        name=NAME, title="Fish Audio S2-Pro (локально)", kind="local", license="Fish Audio Research License",
        license_url="https://huggingface.co/fishaudio/s2-pro/blob/main/LICENSE.md", commercial=False,
        languages=("uk", "en", "ru"), supports=("text_override", "style", "ref_takes", "variability", "seed"),
        cost_note="безкоштовно; повільно на MPS/CPU, швидко на CUDA", requirements=("GPU (MPS/CUDA) бажано", "≈10 ГБ ваг", "Python 3.11 .venv-fish"),
        output_license="CC BY-NC 4.0")

    def __init__(self) -> None:
        self.runner = WorkerRunner()

    def status(self) -> dict:
        from .. import setup
        return setup.engine_status()

    def generate(self, jobs: list, raws: dict, log) -> None:
        pth = config.fish_paths()
        spec = {"repo": pth["repo"], "model": pth["model"],
                "jobs": [{"out": str(raws[i]), "text": j.text, "seed": j.seed, "temperature": j.temperature,
                          "top_p": j.top_p, "max_new": j.max_new,
                          "refs": [{"audio": r["audio"], "text": r["text"]} for r in j.refs]} for i, j in enumerate(jobs)]}
        self.runner.run(pth["py"], str(WORKERS / "fish_worker.py"), spec, lambda m: log(m))

    def similarity(self, pairs: list[dict]) -> dict[str, float]:
        out: dict[str, float] = {}
        if pairs:
            self.runner.run(config.fish_paths()["py"], str(WORKERS / "metrics_worker.py"), {"pairs": pairs},
                            lambda m: out.__setitem__(m["id"], m["similarity"]) if "id" in m else None)
        return out

    def cancel(self) -> None:
        self.runner.cancel()
