# Runbook: перевірити зміну

**Перед кожним комітом: `make verify`** (≤ 20 с, без Chrome): ruff по всіх `tools/*.py` і `tests/`, `node --check` для кожного `web/js/*.js`,
`make guard`, `make check-voices`, швидкі тести (ядро, API, обробка, голоси, guard, дрейф доків).
Перед пушем / для змін студії: `make check` — те саме, що CI (+ e2e у Chrome, покриття ≥ `fail_under`).

## Якщо бракує середовища
`make doctor` показує, чого немає, і підказки (python 3.11/uv, ffmpeg, node, Chrome). `make setup-dev` — досить для verify;
`make setup-refs` (PyCASC) — лише для `make refs`. `make hooks` — pre-commit (guard + ruff).

## Розбір падінь
| Падає | Що робити |
|---|---|
| `ruff` | `.venv/bin/ruff check . --fix`, решту виправити вручну (файл:рядок у виводі) |
| `node --check` | синтаксис модулів `tools/studio/web/js/*.js` (`node --input-type=module --check`) |
| `guard` | у git потрапило аудіо/секрет/тека гри: `git rm --cached <файл>`; дозволені лише FLAC `voices/<нік>/` |
| `check-voices` | текст помилки називає файл і правило (формат, маніфест, оригінал гри, зайвий файл) |
| `tests/test_docs_sync.py` | дрейф: маршрут (`@route` у `routes/*.py`) без запису в docstring `server.py`/`tools/studio/README.md`; цілі make і шляхи в `AGENTS.md`; файл студії > 300 рядків |
| покриття нижче порогу | додати тест; `fail_under` у `pyproject.toml` лише вгору |
| e2e skip | локально без Chrome це норма; у CI — помилка |

Один тест: `.venv/bin/python -I -m pytest -q tests/test_studio_proc.py -k tempo`.
