PY := .venv/bin/python -I

.PHONY: studio test test-nomic

studio:      ## GUI студія запису озвучки Орди
	$(PY) tools/record_studio.py

test:        ## автотест студії з реальним мікрофоном (~2 с запису)
	$(PY) tools/test_record_studio.py

test-nomic:  ## автотест без мікрофона
	$(PY) tools/test_record_studio.py --no-mic
