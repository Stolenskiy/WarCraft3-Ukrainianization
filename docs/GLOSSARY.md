# Глосарій: українські терміни ↔ код

| Укр. | У коді | Значення |
|---|---|---|
| оригінал | `reference/`, `reference-en/`, `Line.ref_path`, `Line.ref_en` | еталонний файл гри: RU із мовного пакета, EN із CASC (локально, не в git) |
| репліка | `Line` (`lid` — стем файлу) | один звуковий файл, напр. `peonyes1`; `Line.game_rel` — шлях у грі |
| група / персонаж | `Group` (`gid`) | юніт або персонаж у каталозі (`peon`, `grunt`) |
| каталог | `Catalog`, `UnitCatalog`, `all_catalogs()` (`cid`) | джерело реплік: раса юнітів, згодом місії |
| раса | `UNIT_RACES`, `reference/units/<race>/` | human / orc / undead / nightelf |
| дубль | take, `takeN.wav` у `audio/self-recorded/` | один запис користувача репліки |
| обрати / затвердити | `approve`, `unapprove` | дубль, що експортується в `game-files/` |
| кошик | `_deleted/`, `delete`/`restore` | видалені дублі (відновлюються) |
| «Як у грі» | `Service.preview`, `/api/preview` | дубль після ланцюжка `_export_filters` (байт у байт як у грі) |
| ланцюжок обробки | `Service._export_filters`, `proc.py` | обрізання → тиша → шум → темп → EQ → гучність |
| обрізання, темп | `trim`, `tempo` | параметри дубля; файл дубля не змінюється |
| EQ-профіль | `eq.py`, `eq_presets.json` | тембр персонажа, пресет `<раса>-<юніт>` |
| voice bible | `docs/voice-bible/` | аркуші характеру й українських реплік |
| гра | `game-files/`, `WC3_GAME_ROOT` | `game-files/` — наші файли для гри; встановлення — `install_voices` |
| встановлення | `install_voices`, `make install-voices` | копіювання обраного в теку гри з бекапом і відкатом |
| голоси спільноти / пакет | `voices/<автор>/`, `voices.py` | опублікований набір FLAC автора, CC BY 4.0 |
| автор | `author`, `voice.json` `id` | нікнейм власника голосу (a-z0-9-); `local` — ваша `game-files/` |
| вибір автора | `voice-choice.json` `{default, race, unit, line}` | чий голос на расу / юніт / репліку; пріоритет line > unit > race > default |
| fallback | позначка в плані встановлення | обраного автора немає для файла → наступний за `default` |
| ШІ-дубль / ШІ-репліка | `source: "ai"`, `"ai": true` у `manifest.json` | синтезоване мовлення; завжди позначається |
| оригінали гри (захист) | `game-files/.originals.json` | відбитки оригіналів; публікація їх відкидає |
| студія | `tools/studio/`, `make studio` | локальний веб-застосунок запису |
| guard | `tools/guard_no_audio.py` | перевірка «у git немає аудіо/секретів» |
| храповик | `fail_under` у `pyproject.toml` | поріг покриття лише зростає |
| транскрипт | `data/local/transcripts-*.json` | текст оригінальної репліки (Whisper) для читання під час запису; лише локально (у git `data/transcripts-*.json` — тривалості) |
