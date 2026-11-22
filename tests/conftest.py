"""Спільні фікстури: тимчасовий корінь проєкту (WC3UA_ROOT) із синтетичними даними.

Аудіо (синус), voice bible і транскрипти — фікстури, тож правки текстів редакторами не ламають
тести, а CI не потребує аудіо гри. Справжні аркуші перевіряє test_real_data_parses.
Ніколи не чіпає справжній стан/аудіо користувача: усе пишеться в tmp.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
TMP_ROOT = Path(tempfile.mkdtemp(prefix="wc3ua-test-"))
os.environ["WC3UA_ROOT"] = str(TMP_ROOT)          # до імпорту studio.*
sys.path.insert(0, str(REPO / "tools"))

# Синтетичні «референси»: аудіо гри не публікується, тож тести (і CI) не залежать від нього.
# Імена файлів справжні; тексти — мінімальні фікстури нижче.
PEON = ["peondeath", *[f"peonpissed{i}" for i in range(1, 5)], "peonready1", "peonwarcry1",
        *[f"peonwhat{i}" for i in range(1, 5)], *[f"peonyes{i}" for i in range(1, 5)],
        *[f"peonyesattack{i}" for i in range(1, 4)]]
FIXTURE = {
    "reference/units/orc/peon": PEON,
    "reference/units/orc/grunt": ["gruntyes1", "gruntwhat1", "gruntpissed1"],
    "reference/units/orc/thrall": ["thrallyes1", "thrallwhat1"],
    "reference/units/human/footman": ["footmanyes1", "footmanwhat1", "footmandeath"],
    "reference-en/units/orc/peon": PEON,             # англійський оригінал є лише в peon
    "reference-en/units/orc/hellscream": ["gromyes1"],  # лише англійський (немає рос. мовного пакета)
}
def synth(path: Path, sec: float = 0.8, freq: int = 440) -> Path:
    """Синтетичний «голос» (синус) у форматі гри."""
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    f"sine=frequency={freq}:sample_rate=22050:duration={sec}", "-ac", "1",
                    "-sample_fmt", "s16", str(path)], check=True)
    return path


BIBLE_ORC = """# Орда (фікстура)

### peon — Орчатник (робітник)
**Характер:** простодушний трудяга.
**Тембр:** низький, хрипкий.

| Фраза | Український текст | Як озвучувати |
|---|---|---|
| yes1–4 | «Зроблю.», «З задоволенням.», «Так, так!», «Добре.» | слухняно-бадьоро |
| what1–4 | «Угу!», «Гей!», «Чого хочеш?», «Чого треба, хазяїне?» | відірвали від роботи |

### grunt — Ґрунт
**Характер:** вояк.

## Поза melee-обсягом
- **thrall — Тралл** — вождь.
"""
TRANSCRIPTS_PEON = {"peonyes1.wav": {"text": "Сделаю.", "duration": 0.8},
                    "peonyes2.wav": {"text": "С удовольствием.", "duration": 0.8},
                    "peondeath.wav": {"text": "Продолжение следует...", "duration": 0.8}}


def _build_fixture() -> None:
    proto = synth(TMP_ROOT / "proto.wav", 0.8)
    for d, names in FIXTURE.items():
        (TMP_ROOT / d).mkdir(parents=True, exist_ok=True)
        for n in names:
            shutil.copy(proto, TMP_ROOT / d / f"{n}.wav")
    (TMP_ROOT / "docs/voice-bible").mkdir(parents=True, exist_ok=True)
    (TMP_ROOT / "docs/voice-bible/orc.md").write_text(BIBLE_ORC, encoding="utf-8")
    (TMP_ROOT / "data").mkdir(exist_ok=True)
    # як у репозиторії: тривалості в data/, синтетичні «оригінальні» тексти — в data/local/ (gitignored)
    (TMP_ROOT / "data/local").mkdir(exist_ok=True)
    (TMP_ROOT / "data/transcripts-orc-peon.json").write_text(
        json.dumps({k: {"duration": v["duration"]} for k, v in TRANSCRIPTS_PEON.items()}))
    (TMP_ROOT / "data/local/transcripts-orc-peon.json").write_text(json.dumps(TRANSCRIPTS_PEON, ensure_ascii=False))


_build_fixture()


@pytest.fixture
def clean_root():
    """Порожній стан перед кожним тестом (референси лишаються)."""
    for d in ("audio", "game-files", "data/studio", "voices"):
        shutil.rmtree(TMP_ROOT / d, ignore_errors=True)
    return TMP_ROOT


@pytest.fixture
def svc(clean_root):
    from studio import core
    return core.Service()


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(TMP_ROOT, ignore_errors=True)
