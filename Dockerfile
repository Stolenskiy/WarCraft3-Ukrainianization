# Студія запису в контейнері: `docker compose up` → http://127.0.0.1:8765
# Студія = stdlib + ffmpeg, тож жодних pip-залежностей (PyCASC, pytest тощо тут не потрібні).
# Дані (audio/, data/, game-files/, voices/, reference*/) монтуються з хоста — див. compose.yaml.
FROM python:3.11-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    STUDIO_BIND=0.0.0.0 \
    WC3_GAME_ROOT=/game

# uid/gid 1000 типово; compose перевизначає через HOST_UID/HOST_GID, щоб файли на хості лишались вашими
RUN useradd --create-home --uid 1000 studio

WORKDIR /app
COPY tools/ tools/
COPY docs/voice-bible/ docs/voice-bible/
COPY data/ data/
RUN mkdir -p audio game-files voices reference reference-en data/studio data/local \
 && chown -R studio:studio /app
USER studio

EXPOSE 8765
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request as u; u.urlopen('http://127.0.0.1:8765/api/catalogs', timeout=4).read()"]

# Усередині контейнера слухаємо 0.0.0.0 (STUDIO_BIND), назовні порт публікується лише на 127.0.0.1 (compose.yaml)
CMD ["python", "-I", "tools/record_studio.py", "--no-browser"]
