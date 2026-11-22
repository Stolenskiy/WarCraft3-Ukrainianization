"""Відкрити теку у файловому менеджері ОС (macOS `open`, Windows `os.startfile`, Linux `xdg-open`). Лише stdlib.
Без графічної оболонки (Docker, SSH) нічого не робить і повертає False."""
from __future__ import annotations

import os
import subprocess
import sys


def open_dir(path) -> bool:
    p = str(path)
    try:
        if sys.platform.startswith("win"):
            os.startfile(p)  # type: ignore[attr-defined]
            return True
        subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", p], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except (OSError, subprocess.SubprocessError):
        return False
