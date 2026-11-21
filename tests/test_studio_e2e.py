"""Наскрізний тест UI у справжньому Chrome з фейковим мікрофоном (Playwright, channel=chrome).

Запуск: make test (потрібен Google Chrome; локально без нього — пропуск, у CI — помилка)
Перевіряє те, що ламається лише в браузері: мікрофон/AudioWorklet, хвилі, клавіші, undo.
"""
import os
import threading

import pytest

pw = pytest.importorskip("playwright.sync_api")

from conftest import TMP_ROOT  # noqa: E402

GAME = TMP_ROOT / "game-files/Units/orc/peon/peonyes1.wav"


@pytest.fixture
def page(svc):
    from studio.server import serve
    httpd = serve(0, open_browser=False, svc=svc)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    with pw.sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="chrome", headless=True, args=[
                "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
                "--autoplay-policy=no-user-gesture-required"])
        except Exception as e:  # noqa: BLE001
            if os.environ.get("CI"):                      # у CI пропуск = непомічена регресія
                raise
            pytest.skip(f"Chrome недоступний: {e}")
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, permissions=["microphone"])
        pg = ctx.new_page()
        pg.on("dialog", lambda d: d.accept())
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.on("console", lambda m: m.type == "error" and "Failed to load resource" not in m.text
              and errors.append(m.text))
        pg.on("response", lambda r: r.status >= 400 and errors.append(f"{r.status} {r.url}"))
        cdp = ctx.new_cdp_session(pg)                    # покриття app.js (інформативно, друкується з -s)
        cdp.send("Profiler.enable")
        cdp.send("Profiler.startPreciseCoverage", {"callCount": False, "detailed": True})
        pg.goto(f"http://127.0.0.1:{httpd.server_address[1]}/")
        pg.wait_for_selector(".cue.on")
        pg.errors = errors
        yield pg
        _print_js_coverage(cdp)
        browser.close()
    httpd.shutdown()


def _print_js_coverage(cdp) -> None:
    """Частка байтів app.js, що виконались (блоки з count=0 віднімаються від охоплюючих)."""
    for script in cdp.send("Profiler.takePreciseCoverage")["result"]:
        if not script["url"].endswith("/static/app.js"):
            continue
        size = max(r["endOffset"] for f in script["functions"] for r in f["ranges"])
        hit = bytearray(size)
        for f in script["functions"]:
            for r in f["ranges"]:
                hit[r["startOffset"]:r["endOffset"]] = (b"\1" if r["count"] else b"\0") * (r["endOffset"] - r["startOffset"])
        print(f"\napp.js coverage: {100 * sum(hit) / size:.0f}%")


def record(pg, sec=1.2):
    n = pg.locator(".take:not(.deleted)").count()
    pg.keyboard.press("Space")
    pg.wait_for_selector("#recBtn.on", timeout=8000)
    pg.wait_for_timeout(int(sec * 1000))
    pg.keyboard.press("Space")
    pg.wait_for_function(f"() => document.querySelectorAll('.take:not(.deleted)').length > {n}", timeout=8000)


def test_full_flow(page):
    pg = page
    assert "Сделаю" in pg.inner_text(".ru-text")
    assert pg.input_value("#ua") == "Зроблю."

    # хвиля оригіналу намальована (є непрозорі пікселі)
    pg.wait_for_function("""() => { const c = document.querySelector('canvas[data-wave="ref"]');
        if (!c || !c.width) return false; const d = c.getContext('2d').getImageData(0,0,c.width,c.height).data;
        for (let i = 3; i < d.length; i += 4) if (d[i]) return true; return false; }""", timeout=8000)

    record(pg)                                           # мікрофон → дубль 1
    assert pg.inner_text(".take .take-head b") == "Дубль 1"
    record(pg)                                           # дубль 2 (миттєвий старт, мікрофон уже відкритий)
    assert pg.locator(".take:not(.deleted)").count() == 2

    # вибір мікрофона: після дозволу є пристрої з назвами; перемикання → запис іде далі
    pg.wait_for_function("() => document.querySelectorAll('#micSel option').length > 1")
    dev = pg.eval_on_selector("#micSel", "s => s.options[s.options.length - 1].value")
    pg.select_option("#micSel", dev)
    pg.wait_for_selector("text=Запис із:")
    record(pg)
    assert pg.locator(".take:not(.deleted)").count() == 3
    pg.reload()
    pg.wait_for_selector(".cue.on")
    assert pg.eval_on_selector("#micSel", "s => s.value") == dev          # запам'ятовано

    pg.locator(".take", has_text="Дубль 1").locator("[data-approve]").click()
    pg.wait_for_selector(".badge-game")
    assert GAME.exists()
    assert "Дубль 1" in pg.inner_text(".approved-banner")

    pg.locator(".take", has_text="Дубль 1").locator("[data-del]").click()   # у кошик + вибір знято
    pg.wait_for_selector("text=у кошику")
    assert not GAME.exists() and pg.locator(".badge-game").count() == 0
    pg.keyboard.press("Meta+z")                          # undo → відновлено й знову обрано
    pg.wait_for_selector(".badge-game")
    assert GAME.exists()

    pg.fill("#ua", "Зроблю, хазяїне.")                   # редагування тексту
    pg.keyboard.press("Enter")
    pg.wait_for_selector("text=✓ збережено")
    assert "Зроблю, хазяїне." in pg.inner_text(".cue.on .ua")

    pg.keyboard.press("ArrowDown")                       # навігація
    assert "удовольствием" in pg.inner_text(".ru-text")

    pg.keyboard.press("ArrowUp")
    with pg.expect_response(lambda r: "/audio/ref-en/" in r.url):   # мова оригіналу → англійська (хвиля вантажить EN)
        pg.click("#optLang [data-lang='en']")
    assert pg.inner_text("#refTag") == "EN"
    pg.keyboard.press("KeyR")                            # R грає вже завантажений EN-оригінал (з кешу)
    pg.reload()                                          # налаштування запам'ятовується
    pg.wait_for_selector(".cue.on")
    assert pg.inner_text("#refTag") == "EN"

    pg.click("#unitBtn")                                 # інша раса → інший юніт
    pg.click("[data-cat='units-human']")
    pg.click("[data-unit='footman']")
    pg.wait_for_function("() => document.querySelector('#unitSub').textContent.startsWith('Альянс')")
    assert pg.locator(".cue").count() == 3
    assert pg.inner_text("#refTag") == "RU"              # англійського немає → російський

    assert not pg.errors, pg.errors


def test_equalizer_panel(page):
    pg = page
    pg.click("#eqPanel summary")
    assert pg.input_value("#eqSel") == "orc-peon"
    pg.wait_for_function("() => document.querySelector('#eqCurve').getContext('2d').getImageData(0,0,248,72).data.some(v => v)")
    pg.locator("input[data-eq='gain'][data-i='1']").fill("-4")                 # рух слайдера → профіль змінено
    pg.click("#eqBypass")
    pg.click("#eqBypass")
    pg.click("#eqNew")
    pg.fill("#eqName", "Мій peon")
    pg.click("#eqSaveNew")
    pg.wait_for_selector("#eqDel")
    assert pg.eval_on_selector("#eqSel", "s => s.selectedOptions[0].text") == "Мій peon"
    pg.reload()
    pg.wait_for_selector(".cue.on")
    pg.click("#eqPanel summary")
    assert pg.eval_on_selector("#eqSel", "s => s.selectedOptions[0].text") == "Мій peon"
    assert pg.input_value("input[data-eq='gain'][data-i='1']") == "-4"
    pg.click("#eqDel")                                                         # confirm → діалог
    assert not pg.errors, pg.errors


def test_screenshot_for_review(page):
    """Скріншот (2 дублі, один обраний) для візуального рев'ю агентом; шлях друкується (-s)."""
    out = os.environ.get("STUDIO_SCREENSHOT") or str(TMP_ROOT.parent / "wc3ua-studio.png")
    record(page, 0.9)
    record(page, 1.6)
    page.locator("[data-approve]").first.click()
    page.wait_for_selector(".badge-game")
    page.evaluate("document.querySelector('#toast').hidden = true")
    page.wait_for_timeout(600)
    page.screenshot(path=str(out))
    print(f"\nscreenshot: {out}")


def _trim_of(pg):
    return pg.evaluate("""async () => { const g = await (await fetch(`/api/group/${S.cat}/${S.unit}`)).json();
        return g.lines.find((l) => l.id === S.phrases[S.idx].id).takes.map((t) => t.trim); }""")


def test_trim_handles(page):
    pg = page
    record(pg, 1.5)
    pg.wait_for_selector(".take .trim-h.start")
    box = pg.locator(".take .wave-box").first.bounding_box()
    h = pg.locator(".take .trim-h.start").first.bounding_box()
    y = h["y"] + h["height"] / 2
    pg.mouse.move(h["x"] + h["width"] / 2, y)            # перетягнути ручку початку на ~30 % хвилі
    pg.mouse.down()
    pg.mouse.move(box["x"] + box["width"] * 0.3, y, steps=6)
    pg.mouse.up()
    pg.wait_for_selector("#toast >> text=обрізано")
    pg.wait_for_selector(".trim-info .trim-t")
    tr = _trim_of(pg)[0]
    assert tr and 0.2 < tr["start"] < 0.7 and tr["end"] > 1.0, tr

    pg.locator(".take .trim-h.end").first.focus()        # ←: крок ручки, а не перехід до іншої репліки
    idx_before = pg.inner_text(".ru-text")
    pg.keyboard.press("ArrowLeft")
    pg.keyboard.press("ArrowLeft")
    pg.wait_for_function("() => document.querySelector('#toast span')?.textContent.includes('обрізано')", timeout=5000)
    pg.wait_for_timeout(700)
    assert pg.inner_text(".ru-text") == idx_before
    tr2 = _trim_of(pg)[0]
    assert abs((tr["end"] - tr2["end"]) - 0.02) < 0.006, (tr, tr2)

    pg.locator("[data-trim-reset]").first.click()        # «Скинути»
    pg.wait_for_function("() => document.querySelectorAll('[data-trim-reset]').length === 0")
    assert _trim_of(pg) == [None]
    assert not pg.errors, pg.errors


def test_trim_moves_marker_and_fit(page):
    pg = page
    record(pg, 1.6)
    pg.wait_for_selector(".take .trim-h.start")
    cv = pg.locator(".take canvas.wave")
    pg.wait_for_function("() => document.querySelector('.take canvas.wave').dataset.markerSec")
    marker = lambda: float(cv.get_attribute("data-marker-sec"))  # noqa: E731
    fit0 = pg.inner_text(".take .fit")
    box = pg.locator(".take .wave-box").first.bounding_box()
    scale = pg.evaluate("() => waves.get(document.querySelector('.take canvas.wave').dataset.wave).opts.scale")
    h = pg.locator(".take .trim-h.start").first.bounding_box()
    y = h["y"] + h["height"] / 2
    pg.mouse.move(h["x"] + h["width"] / 2, y)
    pg.mouse.down()
    start_of = lambda: float(pg.locator(".take .trim-h.start").first.get_attribute("aria-valuenow"))  # noqa: E731
    pg.mouse.move(box["x"] + box["width"] * 0.4, y, steps=6)
    s1, k1 = start_of(), marker()
    pg.mouse.move(box["x"] + box["width"] * 0.55, y, steps=6)     # живе оновлення, ще до відпускання
    s2, k2 = start_of(), marker()
    assert s2 - s1 > 0.1 and abs((k2 - k1) - (s2 - s1)) < 0.02, (s1, s2, k1, k2)
    assert pg.inner_text(".take .fit") != fit0
    start = s2
    pg.mouse.up()
    pg.wait_for_selector("#toast >> text=обрізано")
    # зсув пунктиру в пікселях = зсув ручки в пікселях (в межах кількох px)
    assert abs((marker() - k1) * box["width"] / scale - (start - s1) * box["width"] / scale) < 4
    m1, fit1 = marker(), pg.inner_text(".take .fit")
    pg.reload()
    pg.wait_for_selector(".take .trim-h.start")
    pg.wait_for_function("() => document.querySelector('.take canvas.wave').dataset.markerSec")
    assert abs(float(pg.locator(".take canvas.wave").get_attribute("data-marker-sec")) - m1) < 0.01
    assert pg.inner_text(".take .fit") == fit1
    assert not pg.errors, pg.errors


def test_tempo_fit_to_original_persists(page):
    pg = page
    record(pg, 2.0)                                      # довше за оригінал (0.8 с) → темп > 1
    pg.locator("[data-tempo-toggle]").first.click()
    pg.locator("[data-tempo-fit]").first.click()
    pg.wait_for_selector(".take .tempo-t")
    label = pg.inner_text(".take .tempo-t")
    assert label.startswith("×") and 1.0 < float(label[1:]) <= 1.3, label
    pg.reload()
    pg.wait_for_selector(".take .tempo-t")
    assert pg.inner_text(".take .tempo-t") == label
    assert not pg.errors, pg.errors


def test_game_preview_button_and_processing_toggles(page):
    pg = page
    record(pg, 1.2)
    with pg.expect_response(lambda r: "/api/preview" in r.url and r.status == 200):
        pg.locator("[data-preview]").first.click()
    pg.wait_for_function("() => typeof playing !== 'undefined' && (playing === null || playing.id.startsWith('preview:'))")
    pg.click("#optsMenu summary")
    pg.click("label:has(#optDenoise)")                            # налаштування — на сервері, а не лише в localStorage
    pg.wait_for_function("async () => (await (await fetch('/api/settings')).json()).denoise === true")
    pg.reload()
    pg.wait_for_selector(".cue.on")
    assert pg.is_checked("#optDenoise")
    pg.click("#optsMenu summary")                                 # після перезавантаження меню згорнуте
    pg.click("label:has(#optLoudness)")
    pg.wait_for_function("async () => (await (await fetch('/api/settings')).json()).loudness === false")
    assert not pg.errors, pg.errors


def test_clipping_indicator_and_badge(page):
    pg = page
    assert pg.locator("#clipFlag").count() == 1 and pg.locator("#clipFlag").is_hidden()
    pg.evaluate("Rec.t0 = 123.5; clipCheck(new Float32Array([0.2, -0.5]))")          # без перевантаження
    assert pg.locator("#clipFlag").is_hidden() and "clip" not in pg.get_attribute("#meter", "class")
    pg.evaluate("clipCheck(new Float32Array([0.2, -0.99]))")
    assert pg.locator("#clipFlag").is_visible() and "clip" in pg.get_attribute("#meter", "class")
    pg.wait_for_function("() => !document.querySelector('#meter').classList.contains('clip')", timeout=3000)   # спалах згасає
    assert pg.locator("#clipFlag").is_visible()                                       # індикатор лишається до кінця дубля
    pg.evaluate("Rec.t0 = 999; clipCheck(new Float32Array([0.1]))")                  # новий дубль → скинуто
    assert pg.locator("#clipFlag").is_hidden()
    row = pg.evaluate("takeRow(cur(), {file: 'x.take1.wav', n: 1, clipped: true, exists: true, dur: 1}, false)")
    assert 'class="badge-clip"' in row and "10–15 см" in row
    assert "badge-clip" not in pg.evaluate("takeRow(cur(), {file: 'y.take1.wav', n: 2, clipped: false, exists: true, dur: 1}, false)")


def test_install_modal(page, tmp_path, monkeypatch):
    import install_voices as iv
    from conftest import synth
    game, root = tmp_path / "game", tmp_path / "repo"
    (game / "Mods/m/grunt").mkdir(parents=True)
    (game / "Mods/m/grunt/g.mdx").write_bytes(b"M")
    (game / "Units/orc/peon").mkdir(parents=True)
    (game / "Units/human/footman").mkdir(parents=True)
    os.symlink("../../Mods/m/grunt", game / "Units/orc/grunt")
    for rel in ("orc/peon/peonyes1", "orc/peon/peonwhat1", "orc/grunt/gruntyes1", "human/footman/footmanyes1"):
        synth(root / f"game-files/Units/{rel}.wav")
    monkeypatch.setattr(iv, "GAME", game)
    monkeypatch.setattr(iv, "ROOT", root)
    pg = page
    pg.click("#installBtn")
    pg.wait_for_selector("details.inst-race")
    assert pg.locator("details.inst-race[open]").count() == 0                         # усе згорнуто
    orc = pg.locator('details.inst-race[data-key="orc"]')
    assert "Орда" in orc.inner_text() and "3 з 3 обрано" in orc.locator("> summary").inner_text()
    assert "потребує перетворення теки" in orc.text_content()
    orc.locator("> summary b").click()                                                  # розгорнути / згорнути
    assert orc.evaluate("d => d.open") is True
    orc.locator("> summary b").click()
    assert orc.evaluate("d => d.open") is False
    orc.locator("> summary b").click()
    grunt = pg.locator('details.inst-unit[data-key="orc/grunt"]')
    grunt.locator("> summary input[data-g]").uncheck()                                 # зняти персонажа цілком
    assert "2 з 3 обрано" in orc.locator("> summary").inner_text()
    assert orc.locator("> summary input[data-g]").evaluate("e => e.indeterminate") is True
    pg.evaluate("document.activeElement.blur()")
    pg.keyboard.press("Space")                                                       # у вікні Пробіл не пише
    assert not pg.locator("#recBtn.on").count()
    pg.click("#installGo")
    pg.wait_for_selector("#toast >> text=Встановлено файлів: 3")
    assert (game / "Units/orc/grunt").is_symlink()                                   # не обрано → симлінк лишився
    landed = sorted(p.relative_to(game).as_posix() for p in (game / "Units").rglob("*.wav"))
    assert landed == ["Units/human/footman/footmanyes1.wav", "Units/orc/peon/peonwhat1.wav", "Units/orc/peon/peonyes1.wav"]

    pg.click("#installBtn")                                                           # прибрати лише Альянс
    pg.click("#installMode button[data-mode=uninstall]")
    pg.wait_for_selector('details.inst-race[data-key="orc"]')
    assert pg.locator("details.inst-race").count() == 2
    pg.locator('details.inst-race[data-key="orc"] > summary input[data-g]').uncheck()
    pg.click("#installGo")
    pg.wait_for_selector("#toast >> text=Прибрано з гри файлів: 1")
    assert not (game / "Units/human/footman/footmanyes1.wav").exists() and (game / "Units/orc/peon/peonyes1.wav").exists()
    assert pg.locator("#installModal").is_hidden()


def test_community_voices_flow(page, tmp_path, monkeypatch):
    """«Голоси спільноти»: публікація зі згодою → інший автор для юніта у вікні встановлення → гра отримує його файл."""
    import wave

    import install_voices as iv
    import voices
    from conftest import synth

    def pcm(p):
        with wave.open(str(p), "rb") as w:
            return w.readframes(w.getnframes())

    game = tmp_path / "game"
    (game / "Units").mkdir(parents=True)
    monkeypatch.setattr(iv, "GAME", game)
    monkeypatch.setattr(iv, "ROOT", TMP_ROOT)
    rels = ["Units/orc/peon/peonyes1.wav", "Units/orc/peon/peonwhat1.wav"]
    for r in rels:
        synth(TMP_ROOT / "game-files" / r, freq=300)
    bob_pcm = {r: pcm(TMP_ROOT / "game-files" / r) for r in rels}
    voices.publish("bob", "bob", TMP_ROOT, consent=True)                  # «чужий» голос
    for r in rels:
        synth(TMP_ROOT / "game-files" / r, freq=440)                     # мій локальний
    mine = {r: pcm(TMP_ROOT / "game-files" / r) for r in rels}
    pg = page

    pg.click("#voicesBtn")
    pg.wait_for_selector(".v-row")
    assert pg.locator(".v-row").count() == 2 and "bob" in pg.inner_text("#voicesBody")
    pg.fill("#vNick", "alice")
    pg.click("#vPublish")                                                # без згоди — відмова
    assert not (TMP_ROOT / "voices/alice").exists()
    pg.check("#vConsent")
    pg.click("#vPublish")
    pg.wait_for_selector(".v-result pre")
    assert "git push -u origin voices/alice" in pg.inner_text(".v-result pre")
    assert (TMP_ROOT / "voices/alice/units/orc/peon/peonyes1.flac").is_file()
    assert voices.get_nickname(TMP_ROOT) == "alice"
    with pg.expect_response("**/api/voices/choice"):
        pg.check(".v-row[data-id=bob] [data-von]")                       # bob — серед пріоритетних
    with pg.expect_response("**/api/voices/choice"):
        pg.click(".v-row[data-id=bob] [data-vup]")                       # і вище
    assert "bob" in voices.load_choice(TMP_ROOT)["default"]
    pg.keyboard.press("Escape")
    assert pg.locator("#voicesModal").is_hidden()

    voices.save_choice(TMP_ROOT, {"default": ["local"]})                 # тест: типово — власні
    pg.click("#installBtn")
    pg.wait_for_selector('details.inst-race[data-key="orc"]')
    pg.locator('details.inst-race[data-key="orc"] > summary b').click()
    unit = pg.locator('details.inst-unit[data-key="orc/peon"]')
    assert unit.locator("select[data-vu]").input_value() == ""
    with pg.expect_response("**/api/voices/choice"):
        unit.locator("select[data-vu]").select_option("bob")             # чий голос для юніта
    pg.wait_for_selector("details.inst-unit")
    assert voices.load_choice(TMP_ROOT)["unit"] == {"orc/peon": "bob"}
    unit = pg.locator('details.inst-unit[data-key="orc/peon"]')
    assert unit.evaluate("d => d.open") is False and pg.locator('details.inst-race[data-key="orc"]').evaluate("d => d.open")   # стан дерева збережено
    unit.locator("> summary b").click()
    assert unit.locator("button[data-play]").first.get_attribute("data-a") == "bob"          # звідки файл
    assert unit.locator("select[data-vl]").count() == 2                                       # є вибір для кожного рядка
    unit.locator("button[data-play]").first.click()                       # ▶ без помилок (404 ловить перехоплювач)
    pg.wait_for_timeout(300)
    pg.click("#installGo")
    pg.wait_for_selector("#toast >> text=Встановлено файлів: 2")
    for r in rels:
        assert pcm(game / r) == bob_pcm[r] != mine[r]
    assert not pg.errors
