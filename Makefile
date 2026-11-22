PY := .venv/bin/python -I
PYTHON311 ?= python3.11
CORE_TESTS_A := tests/test_studio_core.py tests/test_eq.py tests/test_install_voices.py tests/test_guard_no_audio.py tests/test_docs_sync.py tests/test_doctor.py
CORE_TESTS_B := tests/test_studio_proc.py tests/test_voices.py
CORE_TESTS_C := tests/test_gameconf.py tests/test_windows.py tests/test_run.py tests/test_textpack.py tests/test_install_pack.py
RUN := $(PY) tools/run.py

.PHONY: studio test test-core lint guard check check-voices verify doctor hooks publish-voice refs \
        setup setup-dev setup-refs install-voices install-text install transcripts-local transcribe uninstall-voices ai-voice docker game-root

verify:      ## «перевір мою зміну» (≤ 20 с, без Chrome): lint + guard + check-voices + test-core
	$(MAKE) --no-print-directory lint guard check-voices test-core

check: lint guard check-voices test   ## те саме, що CI на GitHub (+ e2e у Chrome, покриття) — запускати перед пушем

studio:      ## веб-студія запису озвучки (http://127.0.0.1:8765)
	$(RUN) studio

test:        ## усі тести (ядро, API, UI у Chrome з фейковим мікрофоном) + покриття з порогом
	$(PY) -m pytest -q -s --cov

test-core:   ## швидко, без браузера: ядро, API, обробка, голоси, guard, дрейф доків (дві групи паралельно)
	@$(PY) -m pytest -q $(CORE_TESTS_A) & a=$$!; $(PY) -m pytest -q $(CORE_TESTS_B) & b=$$!; $(PY) -m pytest -q $(CORE_TESTS_C) & c=$$!; \
	  r=0; wait $$a || r=1; wait $$b || r=1; wait $$c || r=1; exit $$r

lint:        ## ruff (усі tools/*.py, tests) + синтаксис JS
	.venv/bin/ruff check . && node --check tools/studio/web/app.js && node --check tools/studio/web/ai.js

guard:       ## у git немає аудіо / ресурсів гри / секретів (дозволені лише FLAC пакетів voices/)
	$(PY) tools/guard_no_audio.py

check-voices: ## пакети голосів спільноти (voices/): формат, маніфест, ліцензія, зайві файли
	$(RUN) check-voices

doctor:      ## чого бракує в середовищі (python 3.11/uv, ffmpeg, node, Chrome/playwright) + підказки
	python3 tools/run.py doctor

hooks:       ## увімкнути git-хуки репозиторію (.githooks/pre-commit: guard + ruff)
	git config core.hooksPath .githooks

refs:        ## оригінали: EN з CASC гри → reference-en/; RU з мовного пакета (RU_PACK=…/ruru.w3mod) → reference/
	$(RUN) refs

transcripts-local: ## тексти оригіналів → data/local/ (gitignored), у git лишаються тривалості (ADR 0005)
	$(RUN) transcripts-local

transcribe:  ## Whisper-розшифровка reference/units/** → data/local/ (потрібні `make refs` і mlx-whisper)
	$(PY) tools/transcribe.py --all

setup: setup-dev setup-refs hooks   ## усе: dev-залежності + PyCASC + git-хуки

setup-dev:   ## .venv на Python 3.11 + requirements-dev (досить для verify/check; без PyCASC)
	test -x .venv/bin/python || (command -v uv >/dev/null && uv venv -q -p 3.11 .venv) || $(PYTHON311) -m venv .venv
	.venv/bin/python -c "import sys; assert sys.version_info[:2] == (3, 11), 'потрібен Python 3.11 у .venv'"
	(command -v uv >/dev/null && uv pip install -q --python .venv/bin/python -r requirements-dev.txt) \
	  || .venv/bin/python -m pip install -q -r requirements-dev.txt

setup-refs:  ## PyCASC і решта requirements.txt (для make refs; PyCASC несумісний з Python 3.12+)
	test -x .venv/bin/python || $(MAKE) setup-dev
	(command -v uv >/dev/null && uv pip install -q --python .venv/bin/python -r requirements.txt) \
	  || .venv/bin/python -m pip install -q -r requirements.txt

install-voices:   ## обрані дублі → гра (без APPLY=1 лише план); бекап і журнал у <гра>/Backups/ua-voices/
	$(RUN) install-voices $(if $(APPLY),--apply,)

install-text:   ## український ТЕКСТ → гра (TARGET=classic-1.31|reforged|legacy; FULL=1 кампанії; REF=<sha>; без APPLY=1 лише план)
	$(RUN) install --target $(or $(TARGET),classic-1.31) --parts text $(if $(FULL),--full,) $(if $(REF),--ref $(REF),) $(if $(APPLY),--apply,)

install:        ## текст + голос разом (ті самі змінні: TARGET, FULL, REF, APPLY)
	$(RUN) install --target $(or $(TARGET),classic-1.31) --parts text,voice $(if $(FULL),--full,) $(if $(REF),--ref $(REF),) $(if $(APPLY),--apply,)

publish-voice: ## власні обрані дублі (game-files/) → voices/<AUTHOR>/ (FLAC); потрібні AUTHOR=<нік> CONSENT=1 (це мій голос, CC BY 4.0)
	$(RUN) publish-voice --author "$(AUTHOR)" $(if $(CONSENT),--consent,)

uninstall-voices: ## прибрати встановлені нами голоси, повернути оригінали
	$(RUN) uninstall-voices

ai-voice:     ## ШІ-варіанти реплік юніта власним голосом (Fish S2-Pro, локально): make ai-voice UNIT=peon [VARIANTS=3]
	$(PY) tools/ai_voice.py --unit $(or $(UNIT),peon) --variants $(or $(VARIANTS),3)

docker:      ## студія в Docker одною командою (http://127.0.0.1:8765); потрібен запущений Docker Desktop
	python3 tools/run.py docker

game-root:   ## показати/задати теку гри: make game-root [GAME=/шлях]
	$(RUN) game-root $(GAME)
