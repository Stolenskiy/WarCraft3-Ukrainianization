"""Спільні фікстури: тимчасовий корінь проєкту (WC3UA_ROOT) з реальними референсами (симлінки).

Ніколи не чіпає справжній стан/аудіо користувача: усе пишеться в tmp.
"""
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
# Імена файлів справжні; тексти/voice bible/карантин — справжні з репозиторію.
PEON = ["peondeath", *[f"peonpissed{i}" for i in range(1, 5)], "peonready1", "peonwarcry1",
        *[f"peonwhat{i}" for i in range(1, 5)], *[f"peonyes{i}" for i in range(1, 5)],
        *[f"peonyesattack{i}" for i in range(1, 4)]]
FIXTURE = {
    "reference/units/orc/peon": PEON,
    "reference/units/orc/grunt": ["gruntyes1", "gruntwhat1", "gruntpissed1"],
    "reference/units/orc/thrall": ["thrallyes1", "thrallwhat1"],
    "reference/units/human/footman": ["footmanyes1", "footmanwhat1", "footmandeath"],
    "reference-en/units/orc/peon": PEON,             # англійський оригінал є лише в peon
}
def synth(path: Path, sec: float = 0.8, freq: int = 440) -> Path:
    """Синтетичний «голос» (синус) у форматі гри."""
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    f"sine=frequency={freq}:sample_rate=22050:duration={sec}", "-ac", "1",
                    "-sample_fmt", "s16", str(path)], check=True)
    return path


def _build_fixture() -> None:
    proto = synth(TMP_ROOT / "proto.wav", 0.8)
    for d, names in FIXTURE.items():
        (TMP_ROOT / d).mkdir(parents=True, exist_ok=True)
        for n in names:
            shutil.copy(proto, TMP_ROOT / d / f"{n}.wav")
    shutil.copytree(REPO / "docs/voice-bible", TMP_ROOT / "docs/voice-bible")
    (TMP_ROOT / "data").mkdir(exist_ok=True)
    for f in [*(REPO / "data").glob("transcripts-*.json"), REPO / "data/watermark-quarantine.json"]:
        shutil.copy(f, TMP_ROOT / "data")


_build_fixture()


@pytest.fixture
def clean_root():
    """Порожній стан перед кожним тестом (референси лишаються)."""
    for d in ("audio", "game-files", "data/studio"):
        shutil.rmtree(TMP_ROOT / d, ignore_errors=True)
    for f in ("data/record-studio-orc.json", "data/record-session-peon.json"):
        (TMP_ROOT / f).unlink(missing_ok=True)
    return TMP_ROOT


@pytest.fixture
def svc(clean_root):
    from studio import core
    return core.Service()


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(TMP_ROOT, ignore_errors=True)
