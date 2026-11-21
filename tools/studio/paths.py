"""Шляхи проєкту. WC3UA_ROOT перевизначає корінь (тести працюють у тимчасовій копії)."""
import os
from pathlib import Path

ROOT = Path(os.environ.get("WC3UA_ROOT") or Path(__file__).resolve().parents[2])
TAKES_ROOT = ROOT / "audio/self-recorded"      # спроби: <catalog>/<group>/<line-stem>.takeN.wav
GAME_FILES = ROOT / "game-files"               # затверджене: game-files/<game_rel>
STATE_DIR = ROOT / "data/studio"               # стан: data/studio/<catalog>.json
SR = 22050                                     # формат гри: WAV PCM s16, 22050 Hz, mono
MIN_TAKE_SEC = 0.25
