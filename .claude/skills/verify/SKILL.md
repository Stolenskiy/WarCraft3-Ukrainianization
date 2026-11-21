---
name: verify
description: Use when you are about to commit, open a PR or claim a change works — runs make verify (lint, guard, check-voices, core tests, under 20 s) and triages failures; falls back to make doctor if the environment is incomplete.
---

# verify

Процедура: **`docs/runbooks/verify.md`** (єдине джерело; не дублюємо).

1. `make verify` перед кожним комітом; `make check` перед пушем або для змін студії (те саме, що CI).
2. Бракує інструментів → `make doctor`, потім `make setup-dev`.
3. Падіння — за таблицею розбору в runbook. `fail_under` лише вгору.
