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
proc.py                               обробка для гри: налаштування, фільтри, гучність, кеш «Як у грі»
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
| Налаштування обробки (`auto_trim`, `denoise`, `loudness`) | `data/studio/settings.json` (gitignored) |
| Кеш «Як у грі» (≤ 200 файлів, найстаріші видаляються) | `data/studio/preview-cache/<hash>.wav` |
| Обраний дубль для гри | `game-files/<Line.game_rel>`, напр. `game-files/Units/orc/peon/peonyes1.wav` |

| Залишений оригінал | `game-files/<Line.game_rel>` (необроблена копія) + перелік у `game-files/.originals.json` |

Формат гри: WAV PCM s16, 22050 Hz, mono. Копія для гри за замовчуванням без тиші на краях.

**Ручне обрізання дубля** (ручки старту/кінця на хвилі): у стані дубля `"trim": {"start": с, "end": с}`
(немає ключа = без обрізання; 0 ≤ start < end ≤ тривалість, end−start ≥ `MIN_TAKE_SEC`). Файл дубля
ніколи не змінюється — обрізання застосовує лише експорт у гру: `Service._export_filters` ставить
`atrim=…,asetpts=PTS-STARTPTS` ПЕРШИМ, потім авто-обрізання тиші (якщо ввімкнене), потім решту обробки.
Зміна `trim` затвердженого дубля одразу перекопіює файл у `game-files`. API: `POST /api/trim
{cid,gid,lid,file,start,end[,auto_trim]}` (`null,null` — скинути). UI: `mountTrim` у `app.js`;
прослуховування дубля в студії теж іде в межах обрізання.

## Залишити оригінал

Для реплік, які не треба переозвучувати (Угу, сміх, крики, звуки атаки/смерті): кнопка «Залишити оригінал (RU|EN)» на картці
(мова — з перемикача оригіналу; клавіша <kbd>O</kbd>). Стан репліки: `"original": {"lang": "ru"|"en", "ts"}`, взаємовиключно з
`approved` (вибір одного знімає інше; `⌘Z`-тост повертає попередній стан). Рахується як «готово»; у списку — чип «ориг. RU/EN»,
на картці — банер зі «Скасувати». Підказка «Можна залишити оригінал» (`catalog.looks_nonverbal`): немає слів у транскрипті
(`no_speech`) або текст — до 3 слів з вигуків (угу, ага, хм, ха-ха…).

- Файл у `game-files/` — БЕЗ обробки (без обрізання, EQ, гучності). WAV 22050 Hz mono s16 копіюється байт-у-байт; інший формат
  (напр. EN-реф з CASC) лише конвертується ffmpeg у формат гри. Інсталяція (`install_voices`) — як звичайний файл.
- `game-files/.originals.json` — `{rel: {lang, sha256}}`. **Публікація голосового пакета МУСИТЬ пропускати всі rel із цього
  файлу**: це аудіо Blizzard, його не комітимо й не поширюємо.
- API: `POST /api/original {cid,gid,lid,lang}` (400 — погана мова / немає такого оригіналу), `POST /api/original/clear {cid,gid,lid}`;
  обидва повертають репліку; у `line_json` — поля `original`, `orig_hint`. Тести: `tests/test_original.py`, e2e `test_keep_original_flow`.

## Обробка файлу для гри (єдиний ланцюжок)

`Service._export_filters` збирає ЄДИНИЙ ланцюжок ffmpeg — його використовують затвердження, `set_trim`/`set_tempo`,
`reexport_group` і «Як у грі» (`Service.preview`), тож прослуховування байт у байт дорівнює файлу гри. Порядок строгий:

| # | Крок | Фільтр | Коли |
|---|---|---|---|
| 1 | ручне обрізання | `atrim=start:end,asetpts=PTS-STARTPTS` | є `trim` дубля |
| 2 | авто-обрізання тиші | `AUTO_TRIM` (silenceremove −45 дБ, запас 0.08/0.12 с) | `auto_trim` |
| 3 | шумоговорення | `afftdn=nf=-45:nr=10,adeclick` | `denoise` (типово вимкнено) |
| 4 | темп | `atempo=<tempo>` (висота та сама) | `tempo` дубля ≠ 1 (0.8–1.3) |
| 5 | EQ персонажа | `eq.to_ffmpeg` | профіль групи |
| 6 | гучність | `volume=±XdB` (≤ ±18 дБ) + `alimiter=limit=0.97:level=0` | `loudness` (типово увімкнено) |

- **Налаштування** — `data/studio/settings.json` `{auto_trim: true, denoise: false, loudness: true}`; `GET/POST /api/settings`;
  перемикачі в шапці (крім «Слухати після запису» — це `localStorage`). Параметри `trim`/`auto_trim` у `/api/approve`,
  `/api/trim`, `/api/eq/reexport` — застарілий явний override. Зміна налаштування вже обрані файли не перезаписує —
  це робить «Застосувати до обраних дублів».
- **Темп** — `tempo` у стані дубля, `POST /api/tempo`; «Під довжину оригіналу» ставить voice/refVoice (1.0–1.3);
  підпис «голос … с» у UI = голос / темп. Затверджений дубль перезаписується одразу.
- **Гучність** — середня гучність (`volumedetect`) озвученої частини оригіналу (`Line.ref_path`, без тиші на краях; кеш
  за (шлях, mtime)) мінус гучність дубля після кроків 1–5; лімітер стелить пік на 0.97 (≈ −0.26 дБFS). `loudnorm`
  не використовується: кліпи короткі.
- **«Як у грі»** — `GET /api/preview?cid=&gid=&lid=&file=`: дубль для будь-якого відомого файлу; ключ кешу — хеш
  ланцюжка + mtime дубля й оригіналу. У браузері відтворюється без живого EQ (він уже всередині).

Оригінал звучить російською або англійською (перемикач у шапці, `localStorage`). Англійські файли —
`reference-en/units/<race>/<unit>/` (`make refs`); `Line.ref_en`, API `/audio/ref-en/...`;
якщо пари немає — звучить інша мова. Без російського мовного пакета (`reference/` порожня) студія
працює лише з англійськими (`Line.has_ru = False`).

## Тести (`tests/`)

| Файл | Що | Час |
|---|---|---|
| `conftest.py` | тимчасовий `WC3UA_ROOT` із **синтетичними** референсами (справжні імена, синус) | — |
| `test_studio_core.py` | Service + HTTP API: інваріанти дублів, відновлення стану, безпека, перевантаження (`peak_db`/`clipped`) | ~2 с |
| `test_studio_proc.py` | обробка: порядок ланцюжка, темп (довжина/висота), гучність і лімітер, шумоговорення, налаштування, «Як у грі» і кеш, API | ~3 с |
| `test_original.py` | «Залишити оригінал»: байти, `.originals.json`, взаємовиключність із дублем, API, план встановлення | ~2 с |
| `test_install_voices.py` | `install_voices`: план/встановлення/відкат, матеріалізація симлінків юнітів (Mods байт-у-байт), API `/api/install*` | ~1 с |
| `test_studio_e2e.py` | Chrome + фейковий мікрофон: запис, хвилі, вибір, кошик/undo, RU/EN, раси, індикатор перевантаження, вікно «Встановити в гру»; друкує покриття app.js і шлях скріншота | ~9 с |

Аудіо гри в тестах і CI не потрібне. Нова поведінка → тест; покриття Python ≥ `fail_under`.

## Перевантаження мікрофона

Під час запису відлік |x| ≥ 0.98 (`clipCheck` в `app.js`) червонить метр і показує «перевантаження» в панелі
запису (раз на дубль). Сервер при `add_take` рахує з wav (stdlib `wave`+`array`) `peak_db` і `clipped`
(≥ 3 відліки |x| ≥ 0.98, `core.wav_peak`) і зберігає їх у дублі (`line_json.takes[]`; у старих дублів полів
немає → `peak_db: null`, `clipped: false`). У рядку дубля — червоний бейдж із порадою, після збереження — тост.

## Встановлення в гру

Кнопка «Встановити в гру» (шапка) відкриває вікно з деревом Раса → Персонаж → файли (згорнуте, чекбокси на кожному
рівні, частковий стан групи, позначки «нове» / «оновиться» / «вже в грі» / «потребує перетворення теки»; пропущене —
окремий блок). `GET /api/install/plan` (сухий прогін, дерево з реальними назвами) → `POST /api/install {files:[game_rel]}`
(`install_voices.apply` лише обраних; невідомий шлях → 400; теку-симлінк перетворюємо, лише якщо обрано її файл).
Режим «Прибрати з гри»: `GET /api/uninstall/plan` (файли з маніфесту) → `POST /api/uninstall {files}`; симлінк теки
повертається, коли в ній не лишилось наших файлів. `make install-voices` / `uninstall-voices` — усе одразу. POST — під тими ж перевірками (X-Studio, Host/Origin). Тека гри — `WC3_GAME_ROOT`
або `/Applications/Warcraft III Classic`; джерело — `game-files/`. Теки юнітів-симлінків матеріалізуються
(реальна тека + симлінки на елементи цілі); деталі, маніфест і відкат — docstring `tools/install_voices.py`
і скіл `game-change`. CLI (`make install-voices` / `uninstall-voices`) працює як раніше.

## Голоси спільноти

Код: `tools/voices.py` (публікація, вибір, декодування; без залежності від студії), `tools/check_voices.py` (перевірка пакетів,
`make check-voices` у `make check` і CI), `Service.voices_json/set_voice_choice/publish_voice/voice_audio`, у `install_voices`
`plan/apply(..., sources={rel: Path})`. Пакет автора — `voices/<нік>/{voice.json, manifest.json, units/<раса>/<юніт>/<файл>.flac}`
(FLAC 22050/mono/s16 = готові файли з `game-files/`; CC BY 4.0, `consent: true`); у git дозволено лише їх (`.gitignore`).

| Що | Де |
|---|---|
| Вибір `{default:[автор…], race:{orc:а}, unit:{"orc/peon":а}, line:{"Units/…wav":а}}` | `data/studio/voice-choice.json` (gitignored) |
| Нікнейм цього комп'ютера (запам'ятовується при публікації) | `data/studio/settings-local.json` (gitignored) |
| Кеш FLAC→wav за sha (для встановлення й ▶) | `data/studio/voice-cache/<sha>.wav` |

Автор `local` = власна `game-files/`. Пріоритет: рядок > юніт > раса > порядок `default`; перший, у кого Є файл, виграє; якщо явно
обраного автора файла немає — наступний за `default` і позначка `fallback`. Без збереженого вибору `default = ["local"]`
(поведінка як раніше). API: `GET /api/voices`, `POST /api/voices/choice`, `POST /api/voices/publish`, `GET /audio/voice/<автор>/<Units/…wav>`
(лише файли з маніфесту з тим самим sha; решта 404); докладно — docstring `server.py`. UI: кнопка «Голоси спільноти» (порядок ↑↓,
публікація зі згодою) і `<select>` автора на рівнях раса / юніт / рядок у вікні встановлення, ▶ — прослухати. Публікація пропускає (і прибирає з пакета) оригінали з `game-files/.originals.json`, а `check_voices` падає, якщо опублікований FLAC збігається з таким оригіналом; обрані дублі з `source: "ai"` позначаються `"ai": true` у manifest.json і «ШІ» в UI. Публікація не запускає git —
повертає команди. Тести: `tests/test_voices.py` (публікація, перевірка, вибір, встановлення суміші, API, traversal) і e2e `test_community_voices_flow`.

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

**Нова дія** (напр. «інверсія фази»): метод у `Service` (під `self.lock`, лог у журнал,
повертає `line_json`), маршрут у `server.py` (`actions`), кнопка в `app.js`, тест на інваріант.

## API (маршрути)

Повний опис тіл і відповідей — docstring `server.py`; тест `tests/test_docs_sync.py` стежить, щоб кожен маршрут був і там, і тут.

| Маршрут | Призначення |
|---|---|
| `GET /api/catalogs`, `GET /api/group/<cid>/<gid>` | каталоги з прогресом; репліки групи |
| `GET /audio/<ref\|ref-en\|take\|game>/…`, `GET /audio/voice/<автор>/…` | аудіо (лише відомі файли) |
| `POST /api/take` | новий дубль (тіло — wav) |
| `POST /api/approve`, `/api/unapprove`, `/api/delete`, `/api/restore`, `/api/text` | вибір, кошик, текст репліки |
| `POST /api/trim`, `/api/tempo`, `GET /api/preview` | обрізання, темп, «Як у грі» |
| `GET/POST /api/settings` | налаштування обробки |
| `GET /api/eq`, `POST /api/eq/profile`, `/api/eq/delete`, `/api/eq/assign`, `/api/eq/reexport` | еквалайзер |
| `GET /api/install/plan`, `POST /api/install`, `GET /api/uninstall/plan`, `POST /api/uninstall`, `POST /api/open-dir` | встановлення в гру |
| `GET /api/voices`, `POST /api/voices/choice`, `POST /api/voices/publish` | голоси спільноти |

## Пастки (вже наступали)

- `AudioContext.resume()` після `await` (діалог дозволу мікрофона) зависає — контекст будимо
  синхронно в `pointerdown/keydown`; декодування — в `OfflineAudioContext`.
- Атрибут `hidden` перекривається `display:flex` — у CSS є `[hidden]{display:none!important}`.
- `screencapture` з агента не працює; візуальна перевірка — `make test` (друкує шлях
  скріншота; `STUDIO_SCREENSHOT=path` — куди зберегти).
