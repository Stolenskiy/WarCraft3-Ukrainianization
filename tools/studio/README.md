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

**Ручне обрізання дубля** (ручки старту/кінця на хвилі): у стані дубля `"trim": {"start": с, "end": с}`
(немає ключа = без обрізання; 0 ≤ start < end ≤ тривалість, end−start ≥ `MIN_TAKE_SEC`). Файл дубля
ніколи не змінюється — обрізання застосовує лише експорт у гру: `Service._export_filters` ставить
`atrim=…,asetpts=PTS-STARTPTS` ПЕРШИМ, потім авто-обрізання тиші (якщо ввімкнене), потім решту обробки.
Зміна `trim` затвердженого дубля одразу перекопіює файл у `game-files`. API: `POST /api/trim
{cid,gid,lid,file,start,end[,auto_trim]}` (`null,null` — скинути). UI: `mountTrim` у `app.js`;
прослуховування дубля в студії теж іде в межах обрізання.

Оригінал звучить російською або англійською (перемикач у шапці, `localStorage`). Англійські файли —
`reference-en/units/<race>/<unit>/` (`make refs`); `Line.ref_en`, API `/audio/ref-en/...`;
якщо пари немає — звучить інша мова. Без російського мовного пакета (`reference/` порожня) студія
працює лише з англійськими (`Line.has_ru = False`).

## Тести (`tests/`)

| Файл | Що | Час |
|---|---|---|
| `conftest.py` | тимчасовий `WC3UA_ROOT` із **синтетичними** референсами (справжні імена, синус) | — |
| `test_studio_core.py` | Service + HTTP API: інваріанти дублів, відновлення стану, безпека, перевантаження (`peak_db`/`clipped`) | ~2 с |
| `test_install_voices.py` | `install_voices`: план/встановлення/відкат, матеріалізація симлінків юнітів (Mods байт-у-байт), API `/api/install*` | ~1 с |
| `test_studio_e2e.py` | Chrome + фейковий мікрофон: запис, хвилі, вибір, кошик/undo, RU/EN, раси, індикатор перевантаження, вікно «Встановити в гру»; друкує покриття app.js і шлях скріншота | ~9 с |

Аудіо гри в тестах і CI не потрібне. Нова поведінка → тест; покриття Python ≥ `fail_under`.

## Перевантаження мікрофона

Під час запису відлік |x| ≥ 0.98 (`clipCheck` в `app.js`) червонить метр і показує «перевантаження» в панелі
запису (раз на дубль). Сервер при `add_take` рахує з wav (stdlib `wave`+`array`) `peak_db` і `clipped`
(≥ 3 відліки |x| ≥ 0.98, `core.wav_peak`) і зберігає їх у дублі (`line_json.takes[]`; у старих дублів полів
немає → `peak_db: null`, `clipped: false`). У рядку дубля — червоний бейдж із порадою, після збереження — тост.

## Встановлення в гру

Кнопка «Встановити в гру» (шапка) → `GET /api/install/plan` (сухий прогін: `copy`, `materialize`, `skipped`, `same`)
→ «Встановити» `POST /api/install` (`install_voices.apply`) / «Прибрати з гри» `POST /api/uninstall`
(`install_voices.uninstall`). POST — під тими ж перевірками (X-Studio, Host/Origin). Тека гри — `WC3_GAME_ROOT`
або `/Applications/Warcraft III Classic`; джерело — `game-files/`. Теки юнітів-симлінків матеріалізуються
(реальна тека + симлінки на елементи цілі); деталі, маніфест і відкат — docstring `tools/install_voices.py`
і скіл `game-change`. CLI (`make install-voices` / `uninstall-voices`) працює як раніше.

## Еквалайзер

Панель «Еквалайзер» у бічній колонці: профіль на персонажа (група), слайдери смуг, крива відгуку,
A/B «З EQ / Без EQ», «Зберегти як новий профіль», оновлення/видалення своїх профілів. Прослуховування дублів
іде через Web Audio (`BiquadFilterNode`) і чується одразу; файли для гри змінюються лише при
виборі дубля та кнопкою «Застосувати до обраних дублів» (`/api/eq/reexport`, запис у журнал кожної репліки).

- Код: `eq.py` (перевірка профілю, `to_ffmpeg`), хук експорту — `Service._export_filters` (EQ іде в кінці ланцюжка).
- Пресети (лише читання, у git): `eq_presets.json` — `{"presets": {id: {name, enabled, gain_db, bands}}}`.
- Дані користувача (gitignored): `data/studio/eq.json` — `{profiles: {id: profile}, assign: {cid: {gid: profile_id}}}`.
- Типовий профіль групи — пресет `<раса>-<gid>` (напр. `orc-peon`), інакше `orc-base` для орків і `neutral` для решти.
- **Нова раса:** додати в `eq_presets.json` пресети з id `<раса>-<папка юніта>` (за аркушами `docs/voice-bible/<раса>.md`;
  кожен — highpass 70–90 Гц, підсилення в межах ±6 дБ) і за потреби `<раса>-base`; `tests/test_eq.py` перевіряє валідність.

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
