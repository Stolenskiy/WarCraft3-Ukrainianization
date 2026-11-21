# Runbook: UI-тест студії (Chrome, фейковий мікрофон)

Файл: `tests/test_studio_e2e.py` (playwright + справжній Chrome, `--use-fake-device-for-media-stream`). Запускається в `make test` / `make check`
(не входить у `make verify`). Потрібно: Google Chrome і playwright (`make setup-dev`; `make doctor`).

1. Фікстура `page` піднімає сервер студії на вільному порту над тимчасовим `WC3UA_ROOT` із синтетичними даними (`tests/conftest.py`).
2. Новий сценарій — функція `test_*(page)`: клікати за селекторами з `index.html`/`app.js`; помилки консолі, `pageerror` і HTTP ≥ 400
   збираються у `page.errors` — перевіряти, що порожньо.
3. Один тест: `.venv/bin/python -I -m pytest -q -s tests/test_studio_e2e.py -k <імʼя>`. З `-s` друкується покриття `app.js` і шлях скріншота;
   `STUDIO_SCREENSHOT=/шлях/studio.png` — куди зберегти. Агент не може робити `screencapture` — дивитись скріншот через цей тест.
4. Без Chrome локально тести пропускаються (skip); у CI (`CI=1`) — падають.
5. Жодного аудіо гри: запис дає фейковий мікрофон, оригінали — синусоїди.
6. Зміна UI → і e2e, і (якщо додано API) тест у `tests/test_studio_core.py`.
