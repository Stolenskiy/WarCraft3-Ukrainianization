PY := .venv/bin/python -I
PYTHON311 ?= python3.11

.PHONY: studio test test-core lint check refs setup

studio:      ## веб-студія запису озвучки (http://127.0.0.1:8765)
	$(PY) tools/record_studio.py

test:        ## усі тести (ядро, API, UI у Chrome з фейковим мікрофоном) + покриття з порогом
	$(PY) -m pytest -q -s --cov

test-core:   ## швидко: лише ядро + API, без браузера
	$(PY) -m pytest -q tests/test_studio_core.py

lint:        ## ruff + синтаксис JS
	.venv/bin/ruff check . && node --check tools/studio/web/app.js

check: lint test   ## те саме, що CI на GitHub — запускати перед комітом

refs:        ## оригінали: EN з CASC гри → reference-en/; RU з мовного пакета (RU_PACK=…/ruru.w3mod) → reference/
	$(PY) tools/build_refs.py

setup:       ## створити .venv на Python 3.11 (PyCASC несумісний з 3.12+) і поставити залежності
	test -x .venv/bin/python || (command -v uv >/dev/null && uv venv -q -p 3.11 .venv) || $(PYTHON311) -m venv .venv
	.venv/bin/python -c "import sys; assert sys.version_info[:2] == (3, 11), 'потрібен Python 3.11 у .venv'"
	(command -v uv >/dev/null && uv pip install -q --python .venv/bin/python -r requirements.txt -r requirements-dev.txt) \
	  || .venv/bin/python -m pip install -q -r requirements.txt -r requirements-dev.txt
