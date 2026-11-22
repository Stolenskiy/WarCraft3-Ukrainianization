#!/usr/bin/env python3
"""ШІ-студія з терміналу: ai-generate / ai-setup / ai-status / ai-consent (див. `python tools/run.py --help`)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from aistudio.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
