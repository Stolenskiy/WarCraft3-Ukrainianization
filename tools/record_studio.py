#!/usr/bin/env python3
"""Студія запису української озвучки (веб-інтерфейс у браузері).

Запуск:  make studio      (або .venv/bin/python -I tools/record_studio.py [--port 8765] [--no-browser])

Відкриється http://127.0.0.1:8765 — сервер слухає лише цей комп'ютер.
Зупинити: Ctrl+C у терміналі.

Де що лежить:
  * дублі — audio/self-recorded/<каталог>/<група>/<репліка>.takeN.wav; кошик — .../_deleted/;
  * обрані для гри — game-files/<шлях як у грі>, напр. game-files/Units/orc/peon/peonyes1.wav;
  * тексти, дублі, рішення, журнал — data/studio/<каталог>.json.
Архітектура й розширення: tools/studio/README.md
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from studio.server import serve  # noqa: E402


def main() -> None:
    port = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 8765
    httpd = serve(port, open_browser="--no-browser" not in sys.argv)
    print(f"Студія: http://127.0.0.1:{httpd.server_address[1]}/   (Ctrl+C — зупинити)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()  # стан уже збережено після кожної дії


if __name__ == "__main__":
    main()
