# feat/ai-character-presets

Готово: пресет персонажа на юніт — висота (±6 пт, форманти не «мультяшаться»), форманти (±20 %, без зміни тону), гроул, простір + хвіст;
лише вбудовані фільтри ffmpeg (`afftfilt` зсуває огинаючу, `asetrate`+`atempo`, `asoftclip`, `aecho`). Код: `tools/studio/character.py`,
`svc/character_svc.py`, `routes/character.py`, UI `web/js/character.js` + `web/css/character.css`; хук у `svc/export.py::_base_filters`.
Стан — `characters` у `data/studio/<cid>.json`; без запису — пропозиція з voice bible (раса + «Обробка»/«Тембр»), вимкнена.
A/B: «A · з пресетом» (сервер `/api/character/audio` + живий EQ) / «B · без». Тести: `test_character.py`, `test_studio_e2e_character.py`.
Далі: пресет на ШІ-варіантах до «Взяти в дублі»; пресети «два голоси» (mortarteam); переслухати пропозиції на справжньому голосі.
Гарячі файли: `svc/export.py`, `web/js/audio.js`, `web/js/eq-live.js`, `web/js/catalog.js`, `web/js/keys.js`, `index.html`, `Makefile`, `tools/run.py`.
