# feat/ai-draft-unit

Готово: «ШІ-чернетка юніта / раси» — `tools/aistudio/draft.py` (план, постановка по завданню на репліку, скасування, «одразу обрати»
через слухача черги), `/api/ai/draft`, `/api/ai/draft/cancel`; прогрес `mix` («живі / ШІ / оригінал», `studio.ai.voice_kind`) у `/api/catalogs`;
UI `web/js/ai-draft.js` + `web/css/ai-draft.css` (шапка юніта, бічна панель, меню юнітів, діалог), черга — групування й «Скасувати всю ШІ-чернетку».
Тести: `tests/test_ai_draft.py`, `tests/test_studio_e2e_draft.py`.
Далі: пакетна генерація кількох реплік за одне завантаження моделі (зараз кожне завдання вантажить модель заново — для раси довго).
Ризики / гарячі файли: `tools/aistudio/jobs.py` (лише параметр `draft` у `submit`), `web/js/ai-queue.js`, `web/js/catalog.js`, `web/index.html`,
`svc/base.py` (`voice_mix`), `routes/aistudio.py`, `server.py` (docstring), `tools/studio/README.md`.
