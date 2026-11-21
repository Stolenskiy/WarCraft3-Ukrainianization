---
name: add-processing-step
description: Use when adding or changing an audio processing step applied to takes before they go into the game (ffmpeg filter chain in Service._export_filters, proc.py, settings toggle, Як у грі preview parity).
---

# add-processing-step

Процедура: **`docs/runbooks/add-processing-step.md`**; таблиця ланцюжка — `tools/studio/README.md`.

Коротко: один ланцюжок `_export_filters` (гучність — останньою), тест у `tests/test_studio_proc.py`, рядок у таблиці README, API — у docstring `server.py`. Після — `make verify`.
