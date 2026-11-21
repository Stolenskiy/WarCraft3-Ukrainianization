PY := .venv/bin/python -I
PYTHON311 ?= python3.11

.PHONY: studio test test-core lint check check-voices publish-voice refs setup install-voices uninstall-voices

studio:      ## веб-студія запису озвучки (http://127.0.0.1:8765)
	$(PY) tools/record_studio.py

test:        ## усі тести (ядро, API, UI у Chrome з фейковим мікрофоном) + покриття з порогом
	$(PY) -m pytest -q -s --cov

test-core:   ## швидко: лише ядро + API, без браузера
	$(PY) -m pytest -q tests/test_studio_core.py tests/test_eq.py tests/test_install_voices.py tests/test_voices.py

lint:        ## ruff + синтаксис JS
	.venv/bin/ruff check . && node --check tools/studio/web/app.js

check-voices: ## пакети голосів спільноти (voices/): формат, маніфест, ліцензія, зайві файли
	$(PY) tools/check_voices.py

check: lint check-voices test   ## те саме, що CI на GitHub — запускати перед комітом

refs:        ## оригінали: EN з CASC гри → reference-en/; RU з мовного пакета (RU_PACK=…/ruru.w3mod) → reference/
	$(PY) tools/build_refs.py

setup:       ## створити .venv на Python 3.11 (PyCASC несумісний з 3.12+) і поставити залежності
	test -x .venv/bin/python || (command -v uv >/dev/null && uv venv -q -p 3.11 .venv) || $(PYTHON311) -m venv .venv
	.venv/bin/python -c "import sys; assert sys.version_info[:2] == (3, 11), 'потрібен Python 3.11 у .venv'"
	(command -v uv >/dev/null && uv pip install -q --python .venv/bin/python -r requirements.txt -r requirements-dev.txt) \
	  || .venv/bin/python -m pip install -q -r requirements.txt -r requirements-dev.txt

install-voices:   ## обрані дублі → гра (без APPLY=1 лише план); бекап і журнал у <гра>/Backups/ua-voices/
	$(PY) tools/install_voices.py $(if $(APPLY),--apply,)

publish-voice: ## власні обрані дублі (game-files/) → voices/<AUTHOR>/ (FLAC); потрібні AUTHOR=<нік> CONSENT=1 (це мій голос, CC BY 4.0)
	$(PY) tools/voices.py publish --author "$(AUTHOR)" $(if $(CONSENT),--consent,)

uninstall-voices: ## прибрати встановлені нами голоси, повернути оригінали
	$(PY) tools/install_voices.py --uninstall
