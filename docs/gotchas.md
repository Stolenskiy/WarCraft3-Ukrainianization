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
- Windows/Docker (НЕ перевірено на реальній Windows; тести — з мок-платформою): реєстр `HKCU\Software\Blizzard Entertainment\Warcraft III` → `Allow Local Files`
  DWORD 1 (джерела — `docs/install-local.md`); `os.symlink` потребує режиму розробника/адміна (інсталятор дає зрозумілу помилку, а теки без симлінків
  працюють); консоль cp1251/cp1252 → `run.py` ставить `PYTHONUTF8=1`, файли відкривати з `encoding="utf-8"`; ключі маніфесту — завжди `/` (`as_posix`).
- Docker: студія слухає `STUDIO_BIND=0.0.0.0` лише в контейнері, порт назовні — тільки `127.0.0.1:8765:8765`; Host-перевірка вимагає, щоб порт хоста
  дорівнював порту сервера (8765), інший порт дасть 403. Симлінки гри через bind-монти Docker Desktop ненадійні → `install-voices` запускати на хості.
- Текст (ADR 0006): upstream без ліцензії — лише кеш `data/local/cache/` + наші перетворення. `Hotkey=` у Reforged-тексті без розмітки: Classic показує клавішу лише через
  `(|cffffcc00A|r)` у Tip; рівні `[|cffffcc00рівень 1|r]` не є «вже з клавішею». Шаблон FDF 1.31 і кириличні шрифти — з CASC самої гри (`_locales/enus|ruru.w3mod`).
- macOS-домени «Allow Local Files»: репак 1.31 — `com.blizzard.WarcraftIII`, Reforged — `com.blizzard.Warcraft III` (з пробілом); на CI/інших ФС регістр імен (`OrcUnitStrings.txt`) зберігаємо за наявним файлом.
- Каталог upstream: `LIGHT[Interface only]/_retail_/` — дужки ламають `glob`; використовуйте `os.listdir`.
