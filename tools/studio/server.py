"""Локальний HTTP-сервер студії (stdlib, без залежностей). Слухає лише 127.0.0.1.

Захист (студія лише для цього комп'ютера):
  - Host має бути 127.0.0.1:<port> або localhost:<port> — інакше 403 (DNS-rebinding);
  - POST вимагає X-Studio: 1 (браузер не надішле його з чужого сайту без CORS) і, якщо є, Origin
    із тим самим хостом; тіло ≤ MAX_UPLOAD.
API:
  GET  /api/catalogs                         каталоги → групи з прогресом і характером
  GET  /api/group/<cid>/<gid>                усі репліки групи зі станом
  GET  /audio/<ref|ref-en|take|game|ai>/<cid>/<gid>/<name>   аудіо (лише відомі файли; ai — ШІ-варіанти з audio/ai/)
  POST /api/take?cid=&gid=&lid=   (тіло — wav)    новий дубль
  POST /api/approve   {cid,gid,lid,file[,trim]}    обрати дубль для гри (trim — застарілий override auto_trim)
  POST /api/unapprove {cid,gid,lid}
  POST /api/original  {cid,gid,lid,lang}          «Залишити оригінал» (lang ru|en): необроблений оригінал → game-files,
                                             запис у game-files/.originals.json (публікація має ці файли пропускати), вибір дубля знімається;
                                             400 — погана мова чи немає такого оригіналу
  POST /api/original/clear {cid,gid,lid}           прибрати оригінал із гри (файл і запис у .originals.json)
  POST /api/delete    {cid,gid,lid,file}           у кошик
  POST /api/restore   {cid,gid,lid,file}
  POST /api/text      {cid,gid,lid,text}
  POST /api/ai/adopt  {cid,gid,lid,file}           КОПІЮЄ ШІ-варіант у дублі: новий дубль `source:"ai"` (далі як будь-який)
  POST /api/ai/discard {cid,gid,lid,file}          сховати ШІ-варіант (репліка містить `ai:[{file,n,engine,cer,similarity,dur,style,adopted}]`)
  POST /api/trim      {cid,gid,lid,file,start,end[,auto_trim]}   ручне обрізання дубля (секунди; null,null — скинути)
  POST /api/tempo     {cid,gid,lid,file,tempo}     темп дубля 0.8–1.3 (atempo, висота та сама; null/1 — скинути)
  GET  /api/settings                         {auto_trim, denoise, loudness} (data/studio/settings.json)
  POST /api/settings  {auto_trim?,denoise?,loudness?}  змінити (булеві); діє на нові експорти, обрані файли
                                             оновлює /api/eq/reexport
  GET  /api/preview?cid=&gid=&lid=&file=     «Як у грі» для будь-якого дубля: wav, зібраний тим самим
                                             ланцюжком і налаштуваннями, що й копія для гри (кеш preview-cache/)
  POST /api/open-dir  {cid,gid}                    відкрити теку game-files у Finder
  GET  /api/eq?cid=&gid=                     {selected, default, stale, profiles:[{id,builtin,name,enabled,gain_db,bands}]}
                                             stale = скільки обраних файлів гри зроблено з іншим EQ/обробкою
  POST /api/eq/profile {cid,gid,profile,id?,assign?}  створити (без id) / оновити власний профіль
  POST /api/eq/delete {cid,gid,id}                 видалити власний профіль (пресети — ні)
  POST /api/eq/assign {cid,gid,profile_id}         профіль групи (null → типовий)
  POST /api/eq/reexport {cid,gid[,trim]}           перезаписати обрані дублі групи з поточним EQ
  GET  /api/install/plan                     сухий прогін: {races:[{id,title,units:[{id,title,files:[{rel,name,status new|update|same,materialize}]}]}],
                                             materialize:[{rel,link,entries}], skipped:[{rel,reason}], same}
  POST /api/install   {files?:[game_rel]}    install_voices.apply лише обраних (без files — усе); невідомий шлях → 400
  GET  /api/uninstall/plan                   те саме дерево, але лише файли з маніфесту (status present|changed|missing)
  POST /api/uninstall {files?:[game_rel]}    прибрати обрані (без files — усе); симлінк теки повертається, коли наших файлів у ній не лишилось
  GET  /api/voices                           голоси спільноти: {authors:[{id,name,local,license,files,bytes,coverage:{раса:{юніт:n}}}] (перший — "local"),
                                             choice:{default,race,unit,line}, nickname, consent_text, license}
  POST /api/voices/choice {default?,race?,unit?,line?,nickname?}  зберегти вибір (data/studio/voice-choice.json; розділ замінюється
                                             цілком, порожнє значення прибирає перевизначення) і нікнейм (settings-local.json); невідомий автор → 400
  POST /api/voices/publish {nickname?,consent}  game-files/ → voices/<нік>/ (FLAC, manifest.json, voice.json); без consent:true або з
                                             нікнеймом поза [a-z0-9-]{2,32} → 400; відповідь: added/updated/removed/total_mb/git (команди; git не запускається)
  GET  /audio/voice/<автор>/<Units/раса/юніт/файл.wav>   прослуховування рядка автора (або "local"); лише файли з маніфесту з тим самим sha, інакше 404
Плани встановлення (install/plan) містять у файлах author/wanted/fallback/alts і ключі authors/choice для вибору голосу.
Кожна дія (крім install*) повертає оновлену репліку (той самий формат, що в /api/group).
"""
from __future__ import annotations

import json
import mimetypes
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

import install_voices  # noqa: F401  (тести підміняють його константи через studio.server.install_voices)

from . import core, routes  # noqa: F401  (імпорт routes реєструє маршрути)
from .routes.registry import Ctx, File, match
from .routes.static import WEB  # noqa: F401

MAX_UPLOAD = 40 * 1024 * 1024


def make_handler(svc: core.Service):
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

        def _host_ok(self) -> bool:
            port = self.server.server_address[1]
            return self.headers.get("Host", "") in (f"127.0.0.1:{port}", f"localhost:{port}")

        def _dispatch(self, method: str, body: bytes = b"") -> None:
            """Маршрут із реєстру → JSON чи файл; помилки домену — 4xx, файлової системи — 500."""
            parts = [unquote(p) for p in urlparse(self.path).path.strip("/").split("/") if p]
            found = match(method, parts)
            if found is None:
                return self._json({"error": "not found"}, 404)
            fn, params = found
            post = method == "POST"
            try:
                res = fn(Ctx(svc, self.path, params, body))
            except (core.StudioError, install_voices.InstallError) as ex:
                bad = post or isinstance(ex, install_voices.InstallError)
                return self._json({"error": str(ex)}, 400 if bad else 404)
            except OSError as ex:
                return self._json({"error": f"помилка файлової системи: {ex}"}, 500)
            except (KeyError, ValueError, TypeError, AttributeError) as ex:
                if post or isinstance(ex, KeyError):
                    return self._json({"error": f"bad request: {ex}"}, 400)
                raise
            self._file(res.path, res.ctype) if isinstance(res, File) else self._json(res)

        def do_GET(self) -> None:
            if not self._host_ok():
                return self._json({"error": "forbidden host"}, 403)
            self._dispatch("GET")

        def do_POST(self) -> None:
            origin = self.headers.get("Origin")
            if (not self._host_ok() or self.headers.get("X-Studio") != "1"
                    or (origin and urlparse(origin).netloc != self.headers.get("Host"))):
                return self._json({"error": "forbidden"}, 403)
            try:
                n = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                return self._json({"error": "bad length"}, 400)
            if not 0 <= n <= MAX_UPLOAD:
                return self._json({"error": "too large"}, 413)
            self._dispatch("POST", self.rfile.read(n))

    return Handler


def serve(port: int = 8765, open_browser: bool = True, svc: core.Service | None = None,
          host: str = "127.0.0.1") -> ThreadingHTTPServer:   # host != 127.0.0.1 лише в Docker (STUDIO_BIND); Host-перевірка та сама
    svc = svc or core.Service()
    httpd = ThreadingHTTPServer((host, port), make_handler(svc))
    httpd.svc = svc
    if open_browser:
        webbrowser.open(f"http://127.0.0.1:{httpd.server_address[1]}/")
    return httpd
