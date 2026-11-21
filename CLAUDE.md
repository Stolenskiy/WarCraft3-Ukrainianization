# CLAUDE.md — робочий контекст для агента

Фанатська українізація Warcraft III Classic (репак lmmortal, клієнт 1.31.1, macOS, Rosetta).
Відповідати українською. Мета — якість «дубляж, що захоплює дух», не «аби було».

**Спершу прочитати:** `docs/STATUS.md` (що зроблено / що далі / рішення — оновлювати в кінці сесії).

## Карта
| Тема | Де |
|---|---|
| Студія запису (власний голос): архітектура, дані, розширення | `tools/studio/README.md` |
| Тексти реплік і характер персонажів (формат таблиць) | `docs/voice-bible/README.md` |
| Будь-яка зміна в теці гри | скіл `game-change` (`.claude/skills/game-change/SKILL.md`) |
| Меню 1.31 / карти / встановлення | `docs/ukrainian-ui-131.md`, `docs/ukrainian-maps.md`, `docs/install-local.md` |
| ElevenLabs (на паузі) | `docs/improve-and-elevenlabs.md` |

## Команди
`make check` — те саме, що CI (ruff + усі тести + поріг покриття); запускати перед кожним комітом.
`make test-core` — швидко без браузера. `make studio` — студія. `make en-refs` — англ. оригінали.
CASC: `.venv/bin/python tools/casc_read.py list "UNITS\\ORC\\"` (фільтр позиційний; `extract --filter … --out …`).
Python — завжди `.venv/bin/python -I`.

## Факти, які дорого відкривати заново
- Гра: `/Applications/Warcraft III Classic`; loose-файли в корені перекривають CASC ("Allow Local Files"=1, увімкнено).
- Голоси: `Units/<раса>/<юніт>/<файл>.wav` (lowercase), WAV s16 22050 Hz mono. `casc_read` «склеює»
  теку з префіксом імені (`heheadhunteryes1.wav`) — реальний шлях з текою (`tools/build_en_refs.py::find`).
- ⚠ `Units/orc/<юніт>` у грі — симлінки в `Mods/Reforged Models/...`; не писати крізь них (скіл `game-change`).
- Меню: fdf Reforged 2.x ламають 1.31 — лише fdf рос. пакета 1.31 + укр. значення.
- macOS: `sudo` без TTY → `osascript … with administrator privileges`; zip з кирилицею → `ditto -x -k`;
  `screencapture` з агента не працює → UI перевіряти `make test` (друкує шлях скріншота).

## Правила
- Комміти без рядків атрибуції. Пуш лише `git push origin` (SSH-аліас `github-ua`); корпоративний акаунт не використовувати.
- Не комітити `reference*/`, `audio/`, `models/`, `game-files/`, `data/studio/`, `.venv*` — аудіо гри й записи не публікуємо.
- Тека гри: лише за скілом `game-change` (бекап + CHANGE-LOG, `Data/` не чіпати, нічого не видаляти).
- Локальні TTS відхилено; не генерувати семпли «на пробу».

## Як працювати швидко і дешево
- Читати точково за картою вище; не сканувати репозиторій.
- Субагенти — лише слабші й лише для повністю специфікованих задач, коли це економить токени; рев'ю — інлайн.
- Нова функція → тест поруч (`tests/`); покриття не знижувати (`fail_under` у `pyproject.toml` — лише вгору).
