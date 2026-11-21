# Студія озвучки (`tools/studio/`)

Локальний веб-застосунок для запису українських дублів поверх російського оригіналу:
обрати репліку → послухати оригінал → записати дублі → обрати один для гри.
Запуск: `make studio` (відкриє http://127.0.0.1:8765). Перевірка: `make check` (як CI).

## Архітектура

```text
web/ (index.html, app.css, app.js)    UI: vanilla JS, без збірки й залежностей
        │  HTTP JSON + wav (лише 127.0.0.1, POST вимагає X-Studio: 1)
server.py                             маршрути → методи Service; API описано в docstring
        │
core.py   Service + Store             стан, дублі, затвердження, журнал; інваріанти — в docstring
        │
catalog.py  Catalog → Group → Line    ЗВІДКИ репліки: референси, транскрипти, voice bible
paths.py                              усі шляхи; WC3UA_ROOT перевизначає корінь (тести)
```

Правило шарів: `catalog` не знає про стан, `core` не знає про HTTP, `server` не містить логіки,
`web` спілкується тільки через API. Запис мікрофона — у браузері (AudioWorklet, мікрофон
тримається відкритим + 0.25 с передзапису); сервер лише конвертує в формат гри через ffmpeg.

## Дані на диску

| Що | Де |
|---|---|
| Стан каталогу (тексти, дублі, вибір, журнал) | `data/studio/<catalog>.json` + `.bak` (попередня версія; gitignored) |
| Дублі | `audio/self-recorded/<catalog>/<group>/<line-stem>.takeN.wav` |
| Кошик (відновлюється) | `audio/self-recorded/<catalog>/<group>/_deleted/` |
| Обраний дубль для гри | `game-files/<Line.game_rel>`, напр. `game-files/Units/orc/peon/peonyes1.wav` |

Формат гри: WAV PCM s16, 22050 Hz, mono. Копія для гри за замовчуванням без тиші на краях.

Оригінал звучить російською або англійською (перемикач у шапці, `localStorage`). Англійські файли —
`reference-en/units/<race>/<unit>/` (`make refs`); `Line.ref_en`, API `/audio/ref-en/...`;
якщо пари немає — звучить інша мова. Без російського мовного пакета (`reference/` порожня) студія
працює лише з англійськими (`Line.has_ru = False`).

## Тести (`tests/`)

| Файл | Що | Час |
|---|---|---|
| `conftest.py` | тимчасовий `WC3UA_ROOT` із **синтетичними** референсами (справжні імена, синус) | — |
| `test_studio_core.py` | Service + HTTP API: інваріанти дублів, відновлення стану, безпека | ~2 с |
| `test_studio_e2e.py` | Chrome + фейковий мікрофон: запис, хвилі, вибір, кошик/undo, RU/EN, раси; друкує покриття app.js і шлях скріншота | ~9 с |

Аудіо гри в тестах і CI не потрібне. Нова поведінка → тест; покриття Python ≥ `fail_under`.

## Розширення

**Нова раса юнітів** (human/undead/nightelf уже підключені): покласти референси в
`reference/units/<race>/<unit>/`, транскрипти в `data/transcripts-<race>-<unit>.json`
(`tools/transcribe.py`), аркуші в `docs/voice-bible/<race>.md`; якщо раси немає в
`UNIT_RACES` (`catalog.py`), додати один рядок. Код UI/ядра не змінюється.

**Нове джерело реплік** (місії кампанії, будівлі, нейтрали): у `catalog.py` створити клас із
полями `id`, `title` і методами `available()`, `groups() -> list[Group]`, `lines(gid) -> list[Line]`
(див. `UnitCatalog` як зразок) і додати його в `all_catalogs()`. Головне — правильний
`Line.game_rel` (шлях файлу в корені гри) і унікальний `Line.id` у межах групи.
Обмеження: формат дубля спільний для всіх (`paths.py`: WAV 22050 mono), а `/api/open-dir`
відкриває теку першої репліки групи — якщо місії потребують іншого, винести це в Catalog.
Додати тест у `tests/test_studio_core.py` (каталог з'являється, репліки вантажаться).

**Нова дія** (напр. «нормалізувати гучність»): метод у `Service` (під `self.lock`, лог у журнал,
повертає `line_json`), маршрут у `server.py` (`actions`), кнопка в `app.js`, тест на інваріант.

## Пастки (вже наступали)

- `AudioContext.resume()` після `await` (діалог дозволу мікрофона) зависає — контекст будимо
  синхронно в `pointerdown/keydown`; декодування — в `OfflineAudioContext`.
- Атрибут `hidden` перекривається `display:flex` — у CSS є `[hidden]{display:none!important}`.
- `screencapture` з агента не працює; візуальна перевірка — `make test` (друкує шлях
  скріншота; `STUDIO_SCREENSHOT=path` — куди зберегти).
