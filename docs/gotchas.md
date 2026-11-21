# Факти, які дорого відкривати заново

Перенесено з CLAUDE.md. Додавайте сюди нову пастку одним пунктом (з посиланням на код).

- Гра: `/Applications/Warcraft III Classic`; loose-файли в корені перекривають CASC ("Allow Local Files"=1, увімкнено).
- Голоси: `Units/<раса>/<юніт>/<файл>.wav` (lowercase), WAV s16 22050 Hz mono. `casc_read` «склеює»
  теку з префіксом імені (`heheadhunteryes1.wav`) — реальний шлях з текою (`tools/build_refs.py::find`).
- ⚠ `Units/orc/<юніт>` у грі — симлінки в `Mods/Reforged Models/...`; не писати крізь них; `install_voices` сам
  матеріалізує такі теки з відкатом (скіл `game-change`).
- Меню: fdf Reforged 2.x ламають 1.31 — лише fdf рос. пакета 1.31 + укр. значення.
- Тексти оригіналів (Whisper) — лише в `data/local/` (gitignored, ADR 0005); у git лише тривалості. Без них студія показує плейсхолдер (`catalog.py::NO_TEXT`); відновити: `make transcripts-local` / `make transcribe`.
- Whisper на звуках без мови «галюцинує» («Продолжение следует…», «Субтитры … DimaTorzok») — це не
  вотермарки; аудіо не різати (`catalog.py::HALLUCINATION_RE`).
- macOS: `sudo` без TTY → `osascript … with administrator privileges`; zip з кирилицею → `ditto -x -k`;
  `screencapture` з агента не працює → UI перевіряти e2e-тестом (`make test` друкує шлях скріншота).
- CASC: `.venv/bin/python tools/casc_read.py list "UNITS\\ORC\\"` (фільтр позиційний; `extract --filter … --out …`).
- PyCASC тягне `requests 2.21` → лише Python 3.11 (тому `make setup-refs` окремо від `setup-dev`).
- Python у цьому репо — завжди `.venv/bin/python -I` (`-I` не додає теку скрипта в `sys.path`: див. `sys.path.insert` у tools/).
