# Хук для вікна «Встановити в гру»: чекбокс «Текст»

Для агента, що переробляє `tools/studio/**` (не чіпайте інсталятор: UI лише викликає Python-функції).

## Бекенд (готовий, `tools/install_pack.py`, `tools/textpack.py`)
- `install_pack.run(target, parts, apply=False, full=False, ref=None, game=None, out=callable) -> 0|1|2` — і план, і встановлення
  (`parts` ⊂ `["text","voice"]`); весь людський вивід іде в `out(str)`. Для UI краще виділити з нього `plan_text` + `prepare`.
- Дані для плану: `install_pack.prepare(target, full, ref, game)` → `(target, game, root, BuildResult)`; `BuildResult.stats["hotkeys"]`,
  `.skipped`, `.source` (коміт, variant, archive_sha256); `install_pack.plan_text(root, res.files)` → `{files:[{rel,status,materialize}], skipped, same}`.
- Застосування: `install_pack.apply_text(root, res.files, meta)`; відкат: `install_pack.uninstall_text(root)` (`install_pack.run_uninstall`).
- Цілі: `textpack.all_targets()` (id, title, status `supported|experimental`, notes). Корінь цілі: `install_pack.target_root(target, game)`.
- Помилки: `PackError`, `textpack.TextPackError`, `install_voices.InstallError` (повідомлення українською, показувати як є).

## Що потрібно в UI
1. Чекбокси «Текст» і «Голос» (за замовчуванням обидва) та список цілей із позначкою EXPERIMENTAL; поле «Тека гри» вже є (gameconf).
2. «Текст» довго завантажує (LIGHT ~2 МБ, FULL ~1 ГБ, опція «з кампаніями»): потрібен фоновий потік + прогрес; `textpack.get_upstream(..., log=cb)`.
3. План показує: версію upstream (коміт), кількість файлів нових/змінених, маркерів клавіш, пропуски (`res.skipped`), попередження EXPERIMENTAL.
4. Нові маршрути (якщо додаватимуться): задокументувати в docstring `server.py` і `tools/studio/README.md` (test_docs_sync).
5. Запис лише після явного підтвердження; ті самі гарантії (`Backups/ua-text/`, відкат) без змін у логіці.
