# Поле «Тека гри» у студії (ЗРОБЛЕНО в feat/modular-redesign: routes/gameroot.py, web/js/gameroot.js, вкладка «Обробка» + вікно встановлення)

Бекенд готовий у `tools/gameconf.py` (без залежностей від студії); UI й маршрути додаються ПІСЛЯ злиття гілок
`feat/windows-docker` і редизайну/модульності студії (щоб не конфліктувати в `app.js`, `server.py`, `core.py`).

## Функції (вже є, покриті `tests/test_gameconf.py`)
- `gameconf.describe() -> {path, source: env|settings|auto|default, valid, platform, env_overrides, settings_file}`
- `gameconf.set_game_root(path) -> Path` (валідує, пише `data/local/settings.json`; `ValueError` з поясненням українською)
- `gameconf.detect() -> [path, …]` (усі валідні кандидати автопошуку, нічого не зберігає)
- `gameconf.clear_game_root()` (повернутись до автопошуку)
- `gameconf.GAME` у `install_voices` обчислюється при імпорті: після зміни шляху в працюючій студії потрібен
  `install_voices.GAME = gameconf.get_game_root()` (інакше — перезапуск). Рекомендовано: читати `gameconf.get_game_root()` у `plan/apply/uninstall`,
  коли `game=None`, замість модульної константи.

## API (додати в `server.py`, ≈ 12 рядків; плюс рядки в docstring сервера й `tools/studio/README.md` — їх вимагає `test_docs_sync`)
```text
GET  /api/game-root            → describe() + {"candidates": detect()}
POST /api/game-root {"path": "<шлях>"}   → describe()            (400 {"error": "…"} якщо ValueError)
POST /api/game-root {"autodetect": true} → describe() після set_game_root(detect()[0]); 400, якщо нічого не знайдено
POST /api/game-root {"clear": true}      → describe() після clear_game_root()
```
POST вимагає `X-Studio: 1` (як решта). Код маршруту:
`data = …; if data.get("clear"): gameconf.clear_game_root() elif data.get("autodetect"): d = gameconf.detect(); … gameconf.set_game_root(d[0]) else: gameconf.set_game_root(data["path"]); return self._json(gameconf.describe())`;
`ValueError` → 400 (додати до існуючого `except (KeyError, ValueError, …)`: він уже віддає `bad request: …`, тож текст помилки обгорнеться — або ловити окремо).

## UI
Поле «Тека гри» у вікні «Встановити в гру» (і/або налаштуваннях): поточний шлях + бейдж джерела (`env`/`settings`/`auto`),
кнопки «Знайти» (GET candidates → вибір зі списку) і «Зберегти» (POST path; показати помилку під полем), «Скинути».
Якщо `env_overrides` (WC3_GAME_ROOT, зокрема Docker: `/game`) — поле лише для читання з поясненням. Невалідна тека → «Встановити» вимкнено.
