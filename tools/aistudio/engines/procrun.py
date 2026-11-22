"""Запуск робочого процесу двигуна, який можна ЗУПИНИТИ (cancel вбиває підпроцес)."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import threading
from pathlib import Path

from .base import Cancelled, EngineError


class WorkerRunner:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._proc: subprocess.Popen | None = None
        self._cancelled = False

    def run(self, py: str, worker: str, spec: dict, on_line) -> None:
        with self._lock:
            self._cancelled = False
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(spec, f)
        try:
            p = subprocess.Popen([py, "-I", worker, f.name], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
            with self._lock:
                self._proc = p
                if self._cancelled:
                    p.kill()
            for line in p.stdout:
                if line.startswith("{"):
                    try:
                        on_line(json.loads(line))
                    except ValueError:
                        pass
            rc = p.wait()
            with self._lock:
                self._proc = None
                was = self._cancelled
            if was:
                raise Cancelled("скасовано")
            if rc != 0:
                raise EngineError(f"робітник {Path(worker).name} завершився з кодом {rc}")
        finally:
            os.unlink(f.name)

    def cancel(self) -> None:
        with self._lock:
            self._cancelled = True
            if self._proc is not None and self._proc.poll() is None:
                self._proc.kill()
