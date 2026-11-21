"""Локальний HTTP-сервер студії (stdlib, без залежностей). Слухає лише 127.0.0.1.

API (усі POST вимагають заголовок X-Studio: 1 — захист від запитів з інших сайтів):
  GET  /api/catalogs                         каталоги → групи з прогресом і характером
  GET  /api/group/<cid>/<gid>                усі репліки групи зі станом
  GET  /audio/<ref|ref-en|take|game>/<cid>/<gid>/<name>   аудіо (лише відомі файли)
  POST /api/take?cid=&gid=&lid=   (тіло — wav)    новий дубль
  POST /api/approve   {cid,gid,lid,file,trim}      обрати дубль для гри
  POST /api/unapprove {cid,gid,lid}
  POST /api/delete    {cid,gid,lid,file}           у кошик
  POST /api/restore   {cid,gid,lid,file}
  POST /api/text      {cid,gid,lid,text}
  POST /api/open-dir  {cid,gid}                    відкрити теку game-files у Finder
Кожна дія повертає оновлену репліку (той самий формат, що в /api/group).
"""
from __future__ import annotations

import json
import mimetypes
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from . import core
from .paths import GAME_FILES

WEB = Path(__file__).resolve().parent / "web"
MAX_UPLOAD = 40 * 1024 * 1024


def make_handler(svc: core.Service):
    actions = {
        "/api/approve": lambda d: svc.approve(d["cid"], d["gid"], d["lid"], d["file"], bool(d.get("trim", True))),
        "/api/unapprove": lambda d: svc.unapprove(d["cid"], d["gid"], d["lid"]),
        "/api/delete": lambda d: svc.delete(d["cid"], d["gid"], d["lid"], d["file"]),
        "/api/restore": lambda d: svc.restore(d["cid"], d["gid"], d["lid"], d["file"]),
        "/api/text": lambda d: svc.set_text(d["cid"], d["gid"], d["lid"], d.get("text", "")),
    }

    class Handler(BaseHTTPRequestHandler):
        server_version = "WC3UAStudio/3"

        def log_message(self, *a) -> None:
            pass

        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, code: int = 200) -> None:
            self._send(code, json.dumps(obj, ensure_ascii=False).encode(), "application/json; charset=utf-8")

        def _file(self, p: Path, ctype: str | None = None) -> None:
            if not p.is_file():
                return self._json({"error": "not found"}, 404)
            ctype = ctype or mimetypes.guess_type(p.name)[0] or "application/octet-stream"
            if ctype.startswith("text/") or ctype.endswith("javascript"):
                ctype += "; charset=utf-8"
            self._send(200, p.read_bytes(), ctype)

        def do_GET(self) -> None:
            parts = [unquote(p) for p in urlparse(self.path).path.strip("/").split("/") if p]
            try:
                if not parts:
                    return self._file(WEB / "index.html")
                if parts[0] == "static" and len(parts) == 2:
                    return self._file(WEB / Path(parts[1]).name)
                if parts == ["api", "catalogs"]:
                    return self._json(svc.catalogs_json())
                if parts[:2] == ["api", "group"] and len(parts) == 4:
                    return self._json(svc.group_json(parts[2], parts[3]))
                if parts[0] == "audio" and len(parts) == 5:
                    return self._file(svc.audio_path(*parts[1:]), "audio/wav")
            except core.StudioError as ex:
                return self._json({"error": str(ex)}, 404)
            self._json({"error": "not found"}, 404)

        def do_POST(self) -> None:
            if self.headers.get("X-Studio") != "1":
                return self._json({"error": "forbidden"}, 403)
            n = int(self.headers.get("Content-Length") or 0)
            if n > MAX_UPLOAD:
                return self._json({"error": "too large"}, 413)
            body = self.rfile.read(n)
            url = urlparse(self.path)
            try:
                if url.path == "/api/take":
                    q = {k: v[0] for k, v in parse_qs(url.query).items()}
                    return self._json(svc.add_take(q["cid"], q["gid"], q["lid"], body))
                data = json.loads(body or b"{}")
                if url.path in actions:
                    return self._json(actions[url.path](data))
                if url.path == "/api/open-dir":
                    svc.lines(data["cid"], data["gid"])  # валідація
                    rel = Path(svc.lines(data["cid"], data["gid"])[0].game_rel).parent
                    d = GAME_FILES / rel
                    d.mkdir(parents=True, exist_ok=True)
                    subprocess.run(["open", str(d)], check=False)
                    return self._json({"ok": True})
            except core.StudioError as ex:
                return self._json({"error": str(ex)}, 400)
            except (KeyError, ValueError, TypeError) as ex:
                return self._json({"error": f"bad request: {ex}"}, 400)
            self._json({"error": "not found"}, 404)

    return Handler


def serve(port: int = 8765, open_browser: bool = True, svc: core.Service | None = None) -> ThreadingHTTPServer:
    svc = svc or core.Service()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), make_handler(svc))
    httpd.svc = svc
    if open_browser:
        subprocess.Popen(["open", f"http://127.0.0.1:{httpd.server_address[1]}/"])
    return httpd
