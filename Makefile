PY := .venv/bin/python -I

.PHONY: studio test test-core lint check en-refs setup-dev

studio:      ## веб-студія запису озвучки (http://127.0.0.1:8765)
	$(PY) tools/record_studio.py

test:        ## усі тести (ядро, API, UI у Chrome з фейковим мікрофоном) + покриття з порогом
	$(PY) -m pytest -q -s --cov

test-core:   ## швидко: лише ядро + API, без браузера
	$(PY) -m pytest -q tests/test_studio_core.py

lint:        ## ruff + синтаксис JS
	.venv/bin/ruff check . && node --check tools/studio/web/app.js

check: lint test   ## те саме, що CI на GitHub — запускати перед комітом

en-refs:     ## англійські оригінали з гри → reference-en/ (для перемикача RU/EN у студії)
	.venv/bin/python tools/casc_read.py extract --filter "war3.w3mod\\_locales\\enus.w3mod\\units\\" --out reference-en-raw
	$(PY) tools/build_en_refs.py

setup-dev:   ## залежності для тестів і лінтера
	uv pip install --python .venv/bin/python -r requirements-dev.txt
