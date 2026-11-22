"""Стан одного каталогу на диску (data/studio/<catalog>.json + .bak)."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

from ..paths import STATE_DIR
from .util import StudioError, new_entry, now


class Store:
    def __init__(self, catalog_id: str) -> None:
        self.catalog_id = catalog_id
        self.path = STATE_DIR / f"{catalog_id}.json"
        self.data = {"version": 3, "groups": {}}
        for p in (self.path, self.bak):           # зіпсований основний файл → остання добра копія
            if p.exists():
                try:
                    self.data = json.loads(p.read_text(encoding="utf-8"))
                    break
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
        else:
            if self.path.exists():
                raise StudioError(f"стан {self.path.name} зіпсований, резервної копії немає — "
                                  "відновіть з git-ігнорованого бекапу або видаліть файл")

    @property
    def bak(self) -> Path:
        return self.path.with_suffix(".json.bak")

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".tmp-", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        if self.path.exists():
            shutil.copy2(self.path, self.bak)      # попередня версія — резерв
        os.replace(tmp, self.path)  # атомарно: стан не зіпсується при збої

    def entry(self, group: str, line: str) -> dict:
        e = self.data["groups"].setdefault(group, {}).setdefault(line, new_entry())
        for k, v in new_entry().items():
            e.setdefault(k, v)
        return e

    def log(self, group: str, line: str, action: str) -> None:
        self.entry(group, line)["history"].append({"ts": now(), "action": action})
