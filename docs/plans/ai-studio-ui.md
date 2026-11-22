# План UI: ШІ-студія (проводка бекенду `tools/aistudio/`)

Бекенд готовий і протестований (гілка feat/ai-studio-backend). UI-фаза лише з'єднує маршрути й екрани з `AiStudio`
(`tools/aistudio/api.py`, чистий Python, усе — dict/list для JSON). Не змішувати з `svc/*`: створити `svc/ai_svc.py`, що тримає
`AiStudio(svc)` і запускає `queue.start()` при старті студії (`queue.stop()` на виході).

## Маршрути (усі POST — JSON, помилки → 400 `{"error": "..."}`; винятки: `ParamsError, RefError, ConsentError, EngineError, JobError, StudioError`)
| Маршрут | Виклик | Відповідь |
|---|---|---|
| GET `/api/ai/status[?deep=1]` | `status(deep)` | готовність, платформа+попередження про швидкість, `consent`, `license_url`, `schema` (межі, пресети стилів), `engines` |
| POST `/api/ai/consent` `{accept}` | `set_consent` | `{ai_consent}` |
| GET `/api/ai/engines` | `engines()` | список двигунів (див. «Вибір двигуна») |
| POST `/api/ai/engine` `{name, upload_consent?, api_key?}` | `set_engine` | оновлений запис двигуна (ключ не повертається) |
| GET `/api/ai/refs?cid&gid&lid[&approved=1]` | `ref_candidates` | усі власні дублі каталогу для вибору |
| POST `/api/ai/generate` `{cid,gid,lid,params}` | `submit` | завдання (`state: queued`, `warnings`, `unsupported`, `license`) |
| POST `/api/ai/again` `{cid,gid,lid,file}` | `again` | «Ще варіант»: ті самі параметри, новий seed, n=1 |
| POST `/api/ai/based-on` `{cid,gid,lid,file}` | `based_on` | параметри варіанта для форми (нічого не запускає) |
| GET `/api/ai/jobs[?state=queued,running]` | `jobs` | усі завдання за порядком черги |
| GET `/api/ai/job?id=` | `job` | одне завдання |
| POST `/api/ai/cancel` `{id}` | `cancel` | завдання зі станом `cancelled` (running: підпроцес убито) |
| GET `/api/ai/events?after=<id>` | `events` | події `{id, ts, job, type: state\|progress\|log, state, progress?, message?}`; опитування раз на 1 с, або SSE через `queue.listeners.append(fn)` |
Наявні `/api/ai/adopt|discard` та `/audio/ai/...` лишаються; `list_ai` не змінювався, `variant_params` дає параметри варіанта.
Доданий маршрут = рядок у docstring `server.py` і `tools/studio/README.md` (`tests/test_docs_sync.py`).

## Параметри (`params` у generate; усе необов'язкове)
`text_override` (текст для моделі: наголоси U+0301, «…», «!!!», теги `[pause]`), `style` (англійська фраза без дужок: `whisper`, `excited` …),
`ref_takes` (імена дублів `peonyes2.take1.wav` або `група/ім'я`; `null` = автовибір затверджених), `variability` 0..1 («Варіативність»,
слайдер; 0.5 типово), `seed` (null = випадковий), `n` 1..8, `engine`. Форма: текст репліки в полі, що редагується (кнопки «…», «!!!», «́»), випадайка
стилів із `schema.style_presets` (позначка verified: docs/pilot) + довільний ввід, слайдер, число варіантів, «Розширені»: seed і вибір референсів.

## Вибір референсів (картка «ШІ-варіанти» → «Голос-референс»)
Перемикач «Затверджені» (типово, автовибір) / «Усі мої дублі». `GET /api/ai/refs` дає рядки `{take,key,gid,line,text,approved,dur,peak_db,clipped,created,same_line}`:
таблиця з чекбоксами (до 5), фільтри «затверджені / усі», позначки «перевантаження» (`clipped`), «та сама репліка» (`same_line`, попередження: референс
повторює цільовий текст), прелистування через наявний `/audio/...` дубля. Вибране → `params.ref_takes` (`key`). У варіанті збережено, які референси
використано, і чи були вони затверджені (`refs[].approved` у побічному json). Референсів з `reference*/` UI не пропонує, а бекенд відхиляє.

## Згода й першопуск
Поки `status.consent == false`, кнопки генерації неактивні, показати `consent_text` + чекбокс → `/api/ai/consent`. Якщо `status.missing` містить `venv|fish-speech|weights` —
панель «Налаштування ШІ»: попередження про швидкість (`platform.warning`), посилання на ліцензію, і команда `python tools/run.py ai-setup --accept-license`
(завантаження 10 ГБ не запускати з браузера без окремого рішення). Усі ШІ-файли в UI мають бейдж «ШІ».

## Вибір двигуна й налаштування двигунів
Випадайка «Двигун» у картці ШІ-варіантів і розділ «Налаштування → ШІ-двигуни»: рядок на `engines[]` — назва, `kind` (значок «локально»/«хмара»), статус
(`ready` зелений; `missing_model`/`missing_env` — що зробити; `missing_key` — поле ключа), мови, ліцензія+`license_url`, **«комерційне: ні»**, `cost_note`,
`requirements`, і які параметри підтримує (`supports`; решту форма вимикає з підказкою «двигун не підтримує», а `warnings`/`unsupported` завдання це
показують). Хмарний двигун: поле API-ключа (пишеться в `data/local/settings.json`, назад не показується; або змінна середовища), окремий чекбокс
«Дозволяю вивантажити мої власні дублі стороннім сервісом» (`upload_consent`) і попередження про вартість (`warnings`). Без згоди генерація не стартує.
Ліцензія результату (`job.license`, `output_license`) показується біля кнопки: «Результат: CC BY-NC 4.0».

## Вікно встановлення голосів і публікація (tools/voices.py → `author_info`)
`author_info` тепер має `ai` (кількість ШІ-реплік) і `ai_license`. У модалці «Встановити в гру»/«Опублікувати» додати рядок, якщо `ai > 0`:
«N реплік — ШІ, ліцензія CC BY-NC 4.0 (лише некомерційне використання); живі записи — CC BY 4.0». У тексті згоди на публікацію —
те саме речення. Після `publish` результат містить пакет з `ai_license`.

## Події й черга в UI
Індикатор «ШІ: N у черзі» (jobs states queued/running), смуга прогресу з `progress.done/total` і `phase` (`generating`, `metrics`), кнопка «Скасувати».
Після `done`: `results[]` → оновити картку (`/api/lines`), нові варіанти мають CER/схожість (можуть бути `null`, якщо немає Whisper). Завдання переживають
перезапуск студії; GPU один: `queue` не запускає двох одночасно, а CLI `ai-generate` поза студією відмовляє, якщо GPU зайнятий.

## Автотривалість і автовибір (feat/ai-autoduration)
`tools/studio/aifit.py` — чисті функції без моделей: `fit(dur, target)` (темп ×0.8–×1.25 під голос оригіналу, пояснення «не влазить»),
`parts/score/rank` (CER, схожість, тривалість після підгонки, пік → 0–100, `rank`, `best`). Рейтинг — у `line.ai` і в `job.results`.
`POST /api/ai/adopt {fit}` ставить дублю `tempo` (наявний механізм темпу дубля); `POST /api/ai/auto-pick` і `auto_pick` у `/api/ai/generate`
(`job.pick`) — лише коли для гри не обрано живий дубль чи оригінал. UI — `web/js/ai-rank.js`.
