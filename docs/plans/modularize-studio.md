# План (фаза 2): модульність студії

Статус: план, НЕ виконано. Виконувати після злиття паралельних гілок (`feat/ui-audit`, `feat/ai`, `feat/orig`), бо вони правлять
`app.js`, `app.css`, `core.py`, `server.py`. Мета: жоден файл > 300 рядків; типова зміна читає ≤ 200 рядків. Без збірки й нових залежностей (ADR 0001).
Номери рядків нижче — станом на `main` 619b6c1; перед стартом перерахувати (`grep -nE "^(async )?function |^const " …`).

## Правила
- Один крок = один коміт = зелений `make check` + e2e. Поведінка не змінюється, лише переміщення (жодних «заодно» правок).
- Покриття Python не знижується; e2e друкує покриття JS — порівнювати до/після (не гірше).
- Перед стартом: `git pull`/rebase на main, `make check` зелений, зафіксувати розміри (`wc -l`).

## 1. `app.js` (1294 р.) → `web/js/*.js` (ES-модулі)
`index.html`: `<script type="module" src="/static/js/main.js">`. Сервер: маршрут `/static/<тека>/<файл>` (зараз лише `/static/<файл>`,
`server.py`: `parts[0]=="static" and len(parts)==2`) — дозволити `css/…` і `js/…` з перевіркою `Path.resolve()` у `WEB` і розширень js/css (+ тест на traversal).
Спільний стан `S`/`EQ`/`Rec`/`Inst`/`Vs` — об'єкти в `state.js`, імпортуються; міжмодульні виклики — прямі імпорти (циклів немає, `main.js` лише збирає).
`node --check` у `make lint` → цикл по `web/js/*.js`.

| Файл | Зміст (поточні рядки) | ≈ рядків |
|---|---|---|
| `util.js` | `$`, `esc`, `sleep`, `fmt`, `initials`, `nFiles`, `mb`, `timeLabel` (5–8, 467, 555, 1101, 1226) | 40 |
| `state.js` | `S`, `ids`, `cur`, `catOf`, `groupOf`, `aurl`, `refLang`, `urlRef`, `urlTake` (10–36, 449–450) | 60 |
| `api.js` | `getJSON`, `post`, `act`, `putPhrase` (14–29, 731–745) | 70 |
| `toast.js` | `toast`, `setUndo`, `runUndo` (951–1012) | 70 |
| `audio.js` | `AC`, `DEC`, `loadBuf`, `voiceSpan`, `play`, `stopPlay`, `markPlaying`, `playPreview` (39–66, 262–303, 942) | 150 |
| `wave.js` | `waves`, `drawWave`, `loadWaves`, `autoDim` (68–102, 647–694, 812) | 150 |
| `eq.js` | `EQ*`, `eqSetup`, `eqRender`, `eqCurve`, `eqReexport` (104–260) | 170 |
| `rec.js` | `Rec`, mic, `ensureMic`, `meterLoop`, `start/stopRec`, `encodeWav` (305–447) | 150 |
| `clip.js` | `CLIP_LEVEL`, `Clip`, `clipCheck` (1065–1090) | 40 |
| `catalog.js` | `loadCatalogs`, `renderUnitGrid`, `toggleUnitPopover`, `openUnit`, `visible`, `renderCues`, `select`, `step`, `nextTodo` (449–548) | 120 |
| `card.js` | `takeRow`, `renderCard`, `bindCard`, `fitInfo`, `saveText` (550–646, 695–757) | 200 |
| `takes.js` | `approve`, `unapprove`, `undoTo`, `del`, `restore` (758–799, 1055) | 80 |
| `trim.js` | `MIN_TRIM`, `AUTO`, `effTrim`, `mountTrim`, `saveTrim`, `resetTrim` (800–891) | 110 |
| `tempo.js` | `TEMPO_*`, `FIT`, `tempoPanel`, `tempoClick`, `saveTempo` (907–941) | 60 |
| `settings.js` | `SETTING_IDS`, `settingsSetup`, `syncOpts`, `renderLang` (892–906, 1013–1054) | 80 |
| `install.js` | `Inst`, `inst*`, `authSelect`, `instChoose`, `openInstall` (1093–1222) | 150 |
| `voices.js` | `Vs`, `vRender`, `vCoverage`, `openVoices`, `vSaveOrder` (1224–1294) | 90 |
| `main.js` | порядок ініціалізації, гарячі клавіші, глобальні обробники (залишок 1013–1064) | 100 |

## 2. `app.css` (418 р.) → `web/css/*.css`
`index.html`: `<link>` на кожен (порядок = каскад). `base.css` (змінні, `[hidden]`, reset, ~40), `topbar.css` (36–98), `layout.css` (99–136),
`card.css` (137–177, 207–274 дублі), `record.css` (178–206, 360–365), `toast.css` (275–320), `eq.css` (321–349), `process.css` (темп, меню «Обробка», 343–359),
`install.css` (366–402), `voices.css` (403–418). Кожен ≤ 150 рядків.

## 3. `server.py` (236 р.) → реєстр маршрутів
Пакет `tools/studio/routes/`: `registry.py` (`ROUTES: dict[(method, path)] → handler`, декоратор `@route("POST", "/api/trim")`, повертає JSON/файл;
єдина обробка помилок `StudioError/InstallError/OSError/KeyError` як зараз), модулі за фічами: `static.py`, `catalogs.py` (catalogs, group, audio, take, approve/unapprove/delete/restore/text),
`process.py` (trim, tempo, preview, settings), `eq.py`, `install.py` (install/uninstall/plan/open-dir), `voices.py`. `server.py` лишає лише HTTP-обгортку: Host/Origin/X-Studio,
розбір шляху, диспетчеризація за реєстром (≤ 120 рядків). `install_tree` → `routes/install.py`. Docstring-перелік API лишається в `server.py`
(`tests/test_docs_sync.py` читає маршрути з реєстру: оновити `server_routes()` — збирати з `ROUTES` і декораторів, лишаючи вимогу docstring+README).

## 4. `core.py` (684 р.) → модулі ≤ 300 рядків (пакет `tools/studio/svc/`)
`Service` лишається фасадом (публічні методи не змінюються, тож `server`/тести не чіпаємо), реалізація — міксини/функції за темами:
`util.py` (`StudioError`, `now`, `take_no`, `file_iso`, `new_entry`, `wav_peak`, `export_take`, константи, ~120), `store.py` (`Store`, ~60),
`service.py` (ядро: каталоги/групи/репліки, `line_json`, `group_json`, `audio_path`, `_adopt_orphans`, ~280), `takes.py` (`add_take`, `approve`, `unapprove`, `delete`, `restore`, `set_text`, ~220),
`export.py` (`_base_filters`, `_export_filters`, `_write_game`, `set_trim`, `set_tempo`, `reexport_group`, `preview`, `get/set_settings`, ~290), `eq_svc.py` (`eq_*`, ~70), `voices_svc.py` (`voices_json`, `set_voice_choice`, `publish_voice`, `voice_audio`, ~60).
`core.py` → тонкий реекспорт (`from .svc import Service, Store, StudioError, …`) для сумісності імпортів у тестах.

## Порядок (кожен пункт — окремий коміт)
1. Тест-сітка: перед рефакторингом — `make check` зелений, зафіксувати покриття; додати e2e-тести на сценарії, що ще не покриті (хоч прикріпити «димовий» тест на кожен JS-модуль).
2. `server.py`: статичні теки `js/`, `css/` + тест на traversal (ще без переміщення коду).
3. CSS → `web/css/*` (найменший ризик; візуально e2e-скріншот до/після).
4. JS: `util`, `state`, `api`, `toast` → `audio`, `wave` → `clip`, `rec` → `eq` → `trim`, `tempo`, `settings` → `catalog`, `card`, `takes` → `install`, `voices` → `main`; `app.js` видалити останнім.
   Після кожного модуля — e2e. Кожен модуль експортує явні `export`; `window.`-глобалів немає (обробники в HTML-атрибутах замінити на `addEventListener`).
5. Реєстр маршрутів (`routes/`), по одній фічі за коміт; docs-sync-тест оновити в тому ж коміті.
6. `core.py` → `svc/*`: спершу `util`, `store`, потім за темами; публічний API `Service` незмінний.
7. Документація: `tools/studio/README.md` (схема файлів, «Розширення»), `AGENTS.md` (карта), `docs/GLOSSARY.md`, ADR 0006 (модулі без збірки); `make lint` — цикл `node --check web/js/*.js`.

## Стратегія тестів і критерії готовності
- `make verify` і `make check` зелені після КОЖНОГО кроку; `fail_under` не знижується (зростає — піднімаємо).
- e2e (`tests/test_studio_e2e.py`) — головна сітка для JS: запис, хвилі, вибір, кошик/undo, RU/EN, обрізання, темп, EQ, вікна встановлення й голосів.
  Додатково: тест «немає помилок консолі/404 при завантаженні модулів» (вже є через `page.errors`).
- Python: тести `test_studio_core.py`/`test_studio_proc.py` лишаються без змін (імпорти `studio.core` працюють через реекспорт).
- Розмірний тест (новий): `tests/test_docs_sync.py` — жоден файл у `tools/studio/**` (крім вендорених даних) не більший за 300 рядків.
- Готово, коли: усі файли ≤ 300 рядків, `app.js` немає, у `AGENTS.md` карта веде в конкретні модулі, прогнозована вартість контексту типової зміни ≤ 530 рядків.
