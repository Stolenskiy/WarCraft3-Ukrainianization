# Runbook: новий крок обробки звуку для гри

Усі експорти (затвердження, `set_trim`/`set_tempo`, `reexport_group`, «Як у грі») йдуть ЄДИНИМ ланцюжком — крок додається один раз.

1. **Ланцюжок:** `ExportMixin._export_filters` (`tools/studio/svc/export.py`) збирає фільтри ffmpeg у строгому порядку
   (обрізання → тиша → шум → темп → EQ → гучність; гучність із лімітером — ЗАВЖДИ останньою). Допоміжне — `tools/studio/proc.py`.
2. **Налаштування** (якщо крок вмикається): ключ у `DEFAULT_SETTINGS` (`proc.py`), `Service.set_settings`, перемикач у вкладці «Обробка» (`web/js/settings.js`, розмітка в `index.html`).
3. **Параметр дубля** (якщо на дубль, як `tempo`): поле в стані дубля, метод `Service` (під `self.lock`, запис у журнал,
   повертає `line_json`), маршрут `@route` у `tools/studio/routes/process.py`, рядок у docstring `server.py` і `tools/studio/README.md`.
4. **Кеш «Як у грі»:** ключ кешу — хеш ланцюжка; новий фільтр має потрапляти в нього автоматично — перевірити тестом.
5. **Тести** в `tests/test_studio_proc.py`: порядок кроку, що «Як у грі» байт у байт = файл для гри, API.
6. **Документація:** рядок у таблиці «Обробка файлу для гри» в `tools/studio/README.md`; докстрінг `proc.py`.
7. `make verify`; UI-кнопка — `docs/runbooks/studio-e2e-test.md`.
