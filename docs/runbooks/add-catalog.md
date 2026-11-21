# Runbook: нове джерело реплік (каталог)

Приклади: місії кампанії, будівлі, нейтральні юніти. Нова **раса юнітів** — без коду (нижче).

## Нова раса юнітів
1. Референси: `reference/units/<race>/<unit>/*.wav` (`make refs`; локально, не в git).
2. Тексти: `data/transcripts-<race>-<unit>.json` (`tools/transcribe.py`); аркуші — `docs/voice-bible/<race>.md`.
3. Якщо раси немає в `UNIT_RACES` (`tools/studio/catalog.py`) — додати один рядок. EQ-пресети — `tools/studio/eq_presets.json`
   (`<раса>-<юніт>`; `tests/test_eq.py` перевіряє).

## Нове джерело (клас каталогу)
1. У `tools/studio/catalog.py` — клас за зразком `UnitCatalog`: `id`, `title`, `available()`, `groups() -> list[Group]`,
   `lines(gid) -> list[Line]`. Критично: правильний `Line.game_rel` (шлях у корені гри) і унікальний `Line.id` у групі.
2. Додати в `all_catalogs()`.
3. Обмеження: формат дубля спільний (`paths.py`: WAV 22050 mono); `/api/open-dir` бере теку першої репліки групи.
4. Тест у `tests/test_studio_core.py` (каталог з'являється, репліки вантажаться); фікстури — `tests/conftest.py` (синтетичні, без аудіо гри).
5. `make verify`; терміни — `docs/GLOSSARY.md`; опис — розділ «Розширення» в `tools/studio/README.md`.
