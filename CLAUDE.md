# CLAUDE.md — робочий контекст для агента

Фанатська українізація Warcraft III Classic (репак lmmortal, клієнт 1.31.1, macOS, Rosetta).
Відповідати українською. Мета — якість «дубляж, що захоплює дух», не «аби було».

## Стан і рішення (не переобговорювати)
- Текстова локалізація (меню, тексти, 203 карти) — **готова і встановлена** в гру.
- Локальні TTS (Piper, XTTS-v2, Fish S2-Pro) — **користувач відхилив** за якістю. Не пропонувати знову.
- ElevenLabs — **на паузі**, доки користувач не дасть ключ (план: `docs/improve-and-elevenlabs.md`).
- Зараз: користувач **сам озвучує Орду** у `tools/record_studio.py` (GUI).

## Команди
| Що | Команда |
|---|---|
| Студія запису (GUI) | `make studio` |
| Автотест студії (без людини) | `make test` (без мікрофона: `make test-nomic`) |
| Прочитати файл із CASC гри | `.venv/bin/python tools/casc_read.py list "UNITS\\ORC\\"` (фільтр — **позиційний**, не `--filter`) |
| Тривалість/формат wav | `afinfo file.wav` |
| Запис мікрофона | `ffmpeg -f avfoundation -i ":0" -ar 22050 -ac 1 -sample_fmt s16 out.wav` (зупинка — `q` у stdin) |

Python — завжди `.venv/bin/python -I` (tkinter, PyCASC, mlx-whisper є тільки там). Fish — `.venv-fish`.

## Факти, які дорого відкривати заново
- **Гра:** `/Applications/Warcraft III Classic`. Loose-файли в корені перекривають CASC при
  `defaults write com.blizzard.WarcraftIII "Allow Local Files" -int 1` (вже ввімкнено).
- **Голоси юнітів у грі:** `Units/orc/<юніт>/<файл>.wav` — ті самі назви, що в `reference/units/orc/<юніт>/`
  (lowercase; APFS нечутливий до регістру). Формат: WAV PCM s16, 22050 Hz, mono.
  `casc_read.py` «склеює» теку з префіксом файлу (`units\orc\peonyes1.wav`, `heheadhunteryes1.wav`) —
  це баг парсера TVFS, реальний шлях — з текою.
- ⚠ `Units/orc/<юніт>` у корені гри здебільшого **симлінки** в `Mods/Reforged Models/...` —
  не писати крізь них; при встановленні озвучки замінювати лінк реальною текою з бекапом.
- **Меню:** fdf формату Reforged 2.x ламають меню 1.31 (порожні кнопки). Працює: fdf із рос. пакета 1.31 +
  українські значення (`docs/ukrainian-ui-131.md`), кириличний шрифт `fonts/frizqt__.ttf` (Nimrod MT).
- **Карти:** назви/описи всередині `war3map.wts` (`tools/wc3map.py`, `build_uk_maps.py`).
- **Дані:** `data/inventory-units.csv` (2401 голосовий файл), `data/transcripts-<раса>-<юніт>.json`
  (`{файл: {text, duration}}`), `data/watermark-quarantine.json` (файли без мови після чищення),
  `docs/voice-bible/<раса>.md` (аркуш персонажа + таблиця `| yes1–4 | «…», «…» | як озвучувати |`).
- **Студія:** стан `data/record-studio-orc.json` (тексти, спроби, затвердження, журнал);
  спроби `audio/self-recorded/<юніт>/*.takeN.wav`, видалені — `_deleted/`; затверджене —
  `game-files/Units/orc/<юніт>/`. `WC3UA_ROOT` перевизначає корінь (для тестів).
- macOS-пастки: `sudo` без TTY → `osascript ... with administrator privileges`; zip з кирилицею → `ditto -x -k`;
  `screencapture` з агента не працює → GUI перевіряти автотестом (`withdraw()` + виклик методів).

## Правила
- Комміти — **без** рядків атрибуції (Co-Authored-By тощо). Пуш тільки через SSH-аліас
  `github-ua` (remote вже налаштований); корпоративний акаунт не використовувати.
- Не комітити `reference/`, `audio/`, `models/`, `game-files/`, `.venv*` (аудіо гри й записи — не публікуємо).
- Тека гри: зміни тільки з бекапом у `Backups/<дата-опис>/` + `CHANGE-LOG.txt`; нічого не видаляти; `Data/` (CASC) не чіпати.

## Як працювати швидко і дешево
- Спершу цей файл, потім точкове читання; не сканувати репозиторій заново.
- Субагенти — лише якщо користувач просить або задача справді паралельна й довга; рев'ю коду — інлайн.
- Кожна зміна інструмента → `make test`; новий інструмент → одразу автотест поруч (`tools/test_*.py`).
- Не генерувати TTS-семпли «на пробу» — користувач вже відкинув локальні рушії.
