#!/usr/bin/env python3
"""ШІ-варіанти реплік юніта з власним голосом користувача (Fish Speech S2-Pro, локально).

Запуск:  make ai-voice UNIT=peon [VARIANTS=3]   (або .venv/bin/python -I tools/ai_voice.py --unit peon)
Читає затверджені дублі зі `self-recorded/`, пише лише в `audio/ai/<каталог>/<юніт>/` (gitignored).
Повторюваний: готові файли пропускає. Подробиці — tools/studio/aigen.py і tools/studio/README.md.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from studio.aigen import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
