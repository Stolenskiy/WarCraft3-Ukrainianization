"""Локальний HTTP-сервер студії (stdlib, без залежностей). Слухає лише 127.0.0.1.

Захист (студія лише для цього комп'ютера):
  - Host має бути 127.0.0.1:<port> або localhost:<port> — інакше 403 (DNS-rebinding);
  - POST вимагає X-Studio: 1 (браузер не надішле його з чужого сайту без CORS) і, якщо є, Origin
    із тим самим хостом; тіло ≤ MAX_UPLOAD.
API:
  GET  /api/catalogs                         каталоги → групи з прогресом і характером
  GET  /api/group/<cid>/<gid>                усі репліки групи зі станом
  GET  /audio/<ref|ref-en|take|game>/<cid>/<gid>/<name>   аудіо (лише відомі файли)
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
  POST /api/trim      {cid,gid,lid,file,start,end[,auto_trim]}   ручне обрізання дубля (секунди; null,null — скинути)
  POST /api/tempo     {cid,gid,lid,file,tempo}     темп дубля 0.8–1.3 (atempo, висота та сама; null/1 — скинути)
  GET  /api/settings                         {auto_trim, denoise, loudness} (data/studio/settings.json)
  POST /api/settings  {auto_trim?,denoise?,loudness?}  змінити (булеві); діє на нові експорти, обрані файли
                                             оновлює /api/eq/reexport
  GET  /api/preview?cid=&gid=&lid=&file=     «Як у грі» для будь-якого дубля: wav, зібраний тим самим
                                             ланцюжком і налаштуваннями, що й копія для гри (кеш preview-cache/)
  POST /api/open-dir  {cid,gid}                    відкрити теку game-files у Finder
  GET  /api/eq?cid=&gid=                     {selected, default, profiles:[{id,builtin,name,enabled,gain_db,bands}]}
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
import subprocess
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import install_voices

from . import core
from .catalog import UNIT_RACES
from .paths import GAME_FILES

WEB = Path(__file__).resolve().parent / "web"
MAX_UPLOAD = 40 * 1024 * 1024


def _opt(d: dict, key: str) -> bool | None:
    """Застарілий явний параметр запиту (trim/auto_trim); немає → береться з налаштувань."""
    return None if d.get(key) is None else bool(d[key])


def install_tree(plan: dict, svc: core.Service) -> dict:
    """Плани install_voices → дерево Раса → Юніт → файли з реальними назвами (запасний варіант — назва теки)."""
    races = {r: t for r, t in UNIT_RACES}
    tree: dict[str, dict] = {}
    for f in plan["files"]:
        parts = f["rel"].split("/")
        race, unit = (parts[1], parts[2]) if len(parts) >= 4 and parts[0].lower() == "units" else ("", "")
        rid = race.lower()
        r = tree.setdefault(rid, {"id": rid, "title": races.get(rid, race or "Інше"), "units": {}})
        if unit not in r["units"]:
            title = unit or "—"
            try:
                title = next((g.title for g in svc.groups(f"units-{rid}") if g.id == unit), title)
            except core.StudioError:
                pass
            r["units"][unit] = {"id": unit, "title": title, "files": []}
        r["units"][unit]["files"].append({**f, "name": parts[-1]})
    order = [r for r, _ in UNIT_RACES]
    out = sorted(tree.values(), key=lambda r: order.index(r["id"]) if r["id"] in order else 99)
    return {**{k: v for k, v in plan.items() if k != "files"},
            "races": [{**r, "units": list(r["units"].values())} for r in out]}


def make_handler(svc: core.Service):
    actions = {
        "/api/approve": lambda d: svc.approve(d["cid"], d["gid"], d["lid"], d["file"], _opt(d, "trim")),
        "/api/unapprove": lambda d: svc.unapprove(d["cid"], d["gid"], d["lid"]),
        "/api/original": lambda d: svc.keep_original(d["cid"], d["gid"], d["lid"], d["lang"]),
        "/api/original/clear": lambda d: svc.clear_original(d["cid"], d["gid"], d["lid"]),
        "/api/delete": lambda d: svc.delete(d["cid"], d["gid"], d["lid"], d["file"]),
        "/api/restore": lambda d: svc.restore(d["cid"], d["gid"], d["lid"], d["file"]),
        "/api/trim": lambda d: svc.set_trim(d["cid"], d["gid"], d["lid"], d["file"], d.get("start"), d.get("end"),
                                            _opt(d, "auto_trim")),
        "/api/tempo": lambda d: svc.set_tempo(d["cid"], d["gid"], d["lid"], d["file"], d.get("tempo")),
        "/api/settings": lambda d: svc.set_settings(d),
        "/api/eq/profile": lambda d: svc.eq_save(d["cid"], d["gid"], d["profile"], d.get("id"), d.get("assign", True)),
        "/api/eq/delete": lambda d: svc.eq_delete(d["cid"], d["gid"], d["id"]),
        "/api/eq/assign": lambda d: svc.eq_assign(d["cid"], d["gid"], d.get("profile_id")),
        "/api/eq/reexport": lambda d: svc.reexport_group(d["cid"], d["gid"], _opt(d, "trim")),
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

        def _host_ok(self) -> bool:
            port = self.server.server_address[1]
            return self.headers.get("Host", "") in (f"127.0.0.1:{port}", f"localhost:{port}")

        def do_GET(self) -> None:
            if not self._host_ok():
                return self._json({"error": "forbidden host"}, 403)
            parts = [unquote(p) for p in urlparse(self.path).path.strip("/").split("/") if p]
            try:
                if not parts:
                    return self._file(WEB / "index.html")
                if parts[0] == "static" and len(parts) == 2:
                    return self._file(WEB / Path(parts[1]).name)
                if parts == ["api", "catalogs"]:
                    return self._json(svc.catalogs_json())
                if parts == ["api", "install", "plan"]:
                    v = svc.voices_json()
                    return self._json({**install_tree(install_voices.plan(), svc),
                                       "authors": [{"id": a["id"], "name": a["name"]} for a in v["authors"]],
                                       "choice": v["choice"]})
                if parts == ["api", "voices"]:
                    return self._json(svc.voices_json())
                if parts[:2] == ["audio", "voice"] and len(parts) >= 4:
                    return self._file(svc.voice_audio(parts[2], "/".join(parts[3:])), "audio/wav")
                if parts == ["api", "uninstall", "plan"]:
                    return self._json(install_tree(install_voices.uninstall_plan(), svc))
                if parts == ["api", "eq"]:
                    q = {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}
                    return self._json(svc.eq_json(q["cid"], q["gid"]))
                if parts == ["api", "settings"]:
                    return self._json(svc.get_settings())
                if parts == ["api", "preview"]:
                    q = {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}
                    return self._file(svc.preview(q["cid"], q["gid"], q["lid"], q["file"]), "audio/wav")
                if parts[:2] == ["api", "group"] and len(parts) == 4:
                    return self._json(svc.group_json(parts[2], parts[3]))
                if parts[0] == "audio" and len(parts) == 5:
                    return self._file(svc.audio_path(*parts[1:]), "audio/wav")
            except (core.StudioError, install_voices.InstallError) as ex:
                return self._json({"error": str(ex)}, 400 if isinstance(ex, install_voices.InstallError) else 404)
            except OSError as ex:
                return self._json({"error": f"помилка файлової системи: {ex}"}, 500)
            except KeyError as ex:
                return self._json({"error": f"bad request: {ex}"}, 400)
            self._json({"error": "not found"}, 404)

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
            body = self.rfile.read(n)
            url = urlparse(self.path)
            try:
                if url.path == "/api/take":
                    q = {k: v[0] for k, v in parse_qs(url.query).items()}
                    return self._json(svc.add_take(q["cid"], q["gid"], q["lid"], body))
                data = json.loads(body or b"{}")
                if url.path in ("/api/install", "/api/uninstall"):
                    chosen = data.get("files")
                    if chosen is not None and not (isinstance(chosen, list) and all(isinstance(x, str) for x in chosen)):
                        raise ValueError("files має бути списком рядків")
                    fn = install_voices.apply if url.path == "/api/install" else install_voices.uninstall
                    return self._json(fn(files=chosen))
                if url.path == "/api/voices/choice":
                    return self._json(svc.set_voice_choice(data))
                if url.path == "/api/voices/publish":
                    return self._json(svc.publish_voice(data.get("nickname"), data.get("consent") is True))
                if url.path in actions:
                    return self._json(actions[url.path](data))
                if url.path == "/api/open-dir":
                    svc.lines(data["cid"], data["gid"])  # валідація
                    rel = Path(svc.lines(data["cid"], data["gid"])[0].game_rel).parent
                    d = GAME_FILES / rel
                    d.mkdir(parents=True, exist_ok=True)
                    subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", str(d)], check=False)
                    return self._json({"ok": True})
            except (core.StudioError, install_voices.InstallError) as ex:
                return self._json({"error": str(ex)}, 400)
            except OSError as ex:
                return self._json({"error": f"помилка файлової системи: {ex}"}, 500)
            except (KeyError, ValueError, TypeError, AttributeError) as ex:
                return self._json({"error": f"bad request: {ex}"}, 400)
            self._json({"error": "not found"}, 404)

    return Handler


def serve(port: int = 8765, open_browser: bool = True, svc: core.Service | None = None) -> ThreadingHTTPServer:
    svc = svc or core.Service()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), make_handler(svc))
    httpd.svc = svc
    if open_browser:
        webbrowser.open(f"http://127.0.0.1:{httpd.server_address[1]}/")
    return httpd
