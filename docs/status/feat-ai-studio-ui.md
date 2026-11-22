# feat/ai-studio-ui

Готово: `routes/aistudio.py` (/api/ai/*), `routes/textinstall.py` (/api/text/*), UI `web/js/ai-{gen,engine,queue,state}.js`, `install-text.js`;
тести `test_ai_routes.py`, `test_studio_e2e_ai.py`. Черга стартує ліниво при першій постановці; події — опитування.
Далі: справжній хмарний двигун; рядок ліцензії ШІ у вікні встановлення голосів/публікації; розділ налаштувань двигунів; SSE (див. ROADMAP).
Ризики: чекбокс «Текст» за замовчуванням вимкнений (план тягне upstream); GPU один — CLI `ai-generate` відмовляє, поки студія генерує.
