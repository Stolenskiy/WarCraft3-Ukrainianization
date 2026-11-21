---
name: add-catalog
description: Use when adding a new source of voice lines to the studio — a new race, campaign missions, buildings or neutral units (a new catalog class in catalog.py, all_catalogs(), fixtures and tests).
---

# add-catalog

Процедура: **`docs/runbooks/add-catalog.md`**; архітектура — `tools/studio/README.md` («Розширення»); терміни — `docs/GLOSSARY.md`.

Коротко: нова раса — лише дані й рядок у `UNIT_RACES`; нове джерело — клас за зразком `UnitCatalog` + `all_catalogs()` + тест. Після — `make verify`.
