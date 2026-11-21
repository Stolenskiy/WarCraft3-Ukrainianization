---
name: studio-e2e-test
description: Use when writing or debugging a browser (UI) test for the recording studio — playwright with real Chrome and a fake microphone, screenshot path, console-error checks, skip rules.
---

# studio-e2e-test

Процедура: **`docs/runbooks/studio-e2e-test.md`**; файл — `tests/test_studio_e2e.py`.

Коротко: `.venv/bin/python -I -m pytest -q -s tests/test_studio_e2e.py -k <імʼя>`; `make doctor` перевіряє Chrome; без Chrome локально — skip, у CI — помилка.
