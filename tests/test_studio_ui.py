"""Аудит UI студії: чи справді чути EQ на кожному шляху прослуховування, і чи список реплік
лишається прокручуваним, коли розгорнуто «Характер і тембр» та «Еквалайзер».

Як міряємо EQ (не «на слух»): init-скрипт обгортає AudioNode.connect і
AudioBufferSourceNode.start — так видно реальний граф від джерела до AC.destination
(`__chain()` — тип і поточні параметри кожного BiquadFilterNode), а все, що йде в
destination, паралельно йде в AnalyserNode (`__measure()` — усереднений спектр того, що
реально грає). Дубль — білий шум, профіль — +12 дБ peaking на 1 кГц, тож «нахил»
(енергія 0.8–1.25 кГц мінус 3–6 кГц) з EQ має бути на ~10 дБ більшим, ніж без EQ.

Нові дефекти фіксуємо тестом з xfail(strict=True): після виправлення він стане зеленим,
а strict змусить зняти позначку.
"""
import subprocess

import pytest

pytest.importorskip("playwright.sync_api")

from conftest import TMP_ROOT  # noqa: E402
from test_studio_e2e import page, record  # noqa: E402,F401  (фікстура Chrome + фейковий мікрофон)

CID, GID = "units-orc", "peon"
BOOST = {"name": "Тест +12 дБ @1 кГц", "enabled": True, "gain_db": 0,
         "bands": [{"type": "peaking", "freq_hz": 1000, "gain_db": 12, "q": 1.0}]}
LOWPASS = {"name": "Тест зріз 500 Гц", "enabled": True, "gain_db": 0,
           "bands": [{"type": "lowpass", "freq_hz": 500, "gain_db": 0, "q": 0.71}]}

TAP = """(() => {
  const realtime = (n) => !(n.context instanceof OfflineAudioContext);
  const oc = AudioNode.prototype.connect;
  AudioNode.prototype.connect = function (dst, ...a) {
    if (dst && dst.context && realtime(this)) {
      (this.__out ||= []).push(dst);
      if (dst instanceof AudioDestinationNode) {
        const ctx = this.context;
        if (!ctx.__tap) { const an = ctx.createAnalyser(); an.fftSize = 2048; an.smoothingTimeConstant = 0; ctx.__tap = an; window.__tap = an; }
        oc.call(this, ctx.__tap);
      }
    }
    return oc.call(this, dst, ...a);
  };
  const os = AudioBufferSourceNode.prototype.start;
  AudioBufferSourceNode.prototype.start = function (...a) { if (realtime(this)) window.__lastSrc = this; return os.apply(this, a); };
  window.__chain = () => {                     // джерело → … → destination, поточні параметри вузлів
    const out = []; let n = window.__lastSrc, guard = 0;
    while (n && n.__out && guard++ < 50) {
      const nx = n.__out[n.__out.length - 1];
      if (nx instanceof AudioDestinationNode) { out.push({ kind: "dest" }); break; }
      if (nx instanceof BiquadFilterNode) out.push({ kind: "biquad", type: nx.type, f: nx.frequency.value, g: nx.gain.value, q: nx.Q.value });
      else if (nx instanceof GainNode) out.push({ kind: "gain", g: nx.gain.value });
      else out.push({ kind: nx.constructor.name });
      n = nx;
    }
    return out;
  };
  window.__measure = async (ms = 600) => {     // середній спектр виходу → енергія смуг, дБ
    const an = window.__tap, n = an.frequencyBinCount, acc = new Float64Array(n), buf = new Float32Array(n);
    let k = 0; const t0 = performance.now();
    while (performance.now() - t0 < ms) {
      an.getFloatFrequencyData(buf);
      for (let i = 0; i < n; i++) acc[i] += Math.pow(10, buf[i] / 10);
      k++; await new Promise((r) => setTimeout(r, 40));
    }
    const hz = an.context.sampleRate / an.fftSize;
    const band = (lo, hi) => { let s = 0; for (let i = Math.ceil(lo / hz); i <= Math.floor(hi / hz); i++) s += acc[i] / k; return 10 * Math.log10(s + 1e-30); };
    return { mid: band(800, 1250), hi: band(3000, 6000), lo: band(150, 300), frames: k };
  };
})();"""


def noise_wav(sec: float = 3.0) -> bytes:
    """Білий шум 22050 Гц (широкий спектр — видно будь-яку смугу EQ)."""
    return subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i",
                           f"anoisesrc=color=white:amplitude=0.3:sample_rate=22050:duration={sec}:seed=7",
                           "-ac", "1", "-sample_fmt", "s16", "-f", "wav", "-"], capture_output=True, check=True).stdout


@pytest.fixture
def eqpage(page, svc):  # noqa: F811 (фікстура з test_studio_e2e)
    """Студія з інструментованим Web Audio, шумовим дублем у поточній репліці й профілем +12 дБ @1 кГц."""
    pg = page
    lid = pg.evaluate("__studio.cur().id")
    svc.add_take(CID, GID, lid, noise_wav())
    svc.eq_save(CID, GID, BOOST)                       # призначається групі
    pg.context.add_init_script(TAP)
    pg.reload()
    pg.wait_for_selector(".take [data-play^='take:']")
    pg.wait_for_function("() => __studio.EQ.prof && __studio.EQ.prof.name.startsWith('Тест')")
    pg.lid = lid
    return pg


def tilt(m) -> float:
    return m["mid"] - m["hi"]


def measure(pg, action, prefix="take:", ms=700):
    """Запустити прослуховування `action()`, дочекатись джерела з id `prefix…`, виміряти вихід і граф."""
    pg.evaluate("__studio.stopPlay()")
    action()
    pg.wait_for_function(f"() => __studio.playing && __studio.playing.id.startsWith('{prefix}')", timeout=8000)
    pg.wait_for_timeout(260)                           # вікно аналізатора (2048 відл.) — без хвоста попереднього звуку
    chain = pg.evaluate("__chain()")
    m = pg.evaluate(f"__measure({ms})")
    assert m["frames"] >= 5, m
    return m, chain


def baseline(pg):
    """«Нахил» дубля без EQ: та сама кнопка A/B у режимі «без EQ»."""
    pg.click("#eqPanel summary")
    pg.click("#eqBypass")
    m, chain = measure(pg, lambda: pg.click(".take [data-play^='take:']"))
    assert not [n for n in chain if n["kind"] == "biquad"], chain        # bypass справді обходить EQ
    pg.click("#eqBypass")
    pg.evaluate("__studio.stopPlay()")
    return tilt(m)


def has_boost(chain) -> bool:
    return any(n["kind"] == "biquad" and n["type"] == "peaking" and abs(n["f"] - 1000) < 1 and abs(n["g"] - 12) < 0.01
               for n in chain)


# ------------------------------------------------------------------ EQ: шляхи, де він ПРАЦЮЄ (регресійний захист)

def test_eq_applied_on_every_take_playback_path(eqpage):
    pg = eqpage
    t0 = baseline(pg)
    paths = {
        "▶ дубля": lambda: pg.click(".take [data-play^='take:']"),
        "клік по хвилі": lambda: pg.click(".take canvas.wave", position={"x": 30, "y": 10}),
        "Оригінал → дубль": lambda: pg.click(".take [data-ab]"),
        "клавіша L": lambda: (pg.evaluate("document.activeElement.blur()"), pg.keyboard.press("KeyL")),
        "клавіша B": lambda: (pg.evaluate("document.activeElement.blur()"), pg.keyboard.press("KeyB")),
    }
    for name, act in paths.items():
        m, chain = measure(pg, act)
        assert has_boost(chain), (name, chain)
        assert chain[-1] == {"kind": "dest"}, (name, chain)
        d = tilt(m) - t0
        assert 8 < d < 15, f"{name}: EQ +12 дБ дає лише {d:.1f} дБ"
    assert not pg.errors, pg.errors


def test_eq_follows_profile_switch_and_live_slider(eqpage, svc):
    pg = eqpage
    t0 = baseline(pg)
    lp_id = svc.eq_save(CID, GID, LOWPASS, assign=False)["saved_id"]   # у списку, не призначений
    pg.evaluate("__studio.eqLoad()")
    pg.wait_for_function("() => __studio.EQ.data.profiles.some((p) => p.name === 'Тест зріз 500 Гц')")
    lp = pg.evaluate("__studio.EQ.data.profiles.find((p) => p.name === 'Тест зріз 500 Гц').id")
    assert lp_id
    pg.select_option("#eqSel", lp)                                     # перемкнути профіль → наступне ▶ з ним
    pg.wait_for_function(f"() => __studio.EQ.id === '{lp}'")
    m, chain = measure(pg, lambda: pg.click(".take [data-play^='take:']"))
    assert [n["type"] for n in chain if n["kind"] == "biquad"] == ["lowpass"], chain
    assert tilt(m) - t0 > 15, tilt(m) - t0                             # 3–6 кГц придушено

    boost = pg.evaluate("__studio.EQ.data.profiles.find((p) => p.name === 'Тест +12 дБ @1 кГц').id")
    pg.select_option("#eqSel", boost)
    pg.wait_for_function(f"() => __studio.EQ.id === '{boost}'")
    measure(pg, lambda: pg.click(".take [data-play^='take:']"), ms=200)
    sl = pg.locator("input[data-eq='gain'][data-i='0']")              # слайдер під час звучання → живе оновлення
    sl.evaluate("(e) => { e.value = -12; e.dispatchEvent(new Event('input', { bubbles: true })); }")
    pg.wait_for_timeout(260)
    chain = pg.evaluate("__chain()")
    assert any(n["kind"] == "biquad" and abs(n["g"] + 12) < 0.01 for n in chain), chain
    m = pg.evaluate("__measure(500)")
    assert tilt(m) - t0 < -6, tilt(m) - t0
    assert not pg.errors, pg.errors


def test_eq_on_autoplay_after_recording(eqpage):
    pg = eqpage
    assert pg.is_checked("#optAutoplay")
    pg.evaluate("document.activeElement.blur()")
    record(pg, 1.0)
    pg.wait_for_function("() => __studio.playing && __studio.playing.id.startsWith('take:')", timeout=8000)
    assert has_boost(pg.evaluate("__chain()")), pg.evaluate("__chain()")


def test_game_preview_not_double_eq_and_export_has_profile(eqpage, svc):
    """«▶ У грі» — файл уже з EQ (сервер), у браузері EQ вдруге не накладається; файл для гри теж з профілем."""
    pg = eqpage
    t0 = baseline(pg)
    m, chain = measure(pg, lambda: pg.click(".take [data-preview]"), prefix="preview:")
    assert chain == [{"kind": "dest"}], chain                          # без живого EQ
    d = tilt(m) - t0
    assert 8 < d < 15, f"«У грі»: {d:.1f} дБ (≈24 — подвійний EQ, ≈0 — EQ немає)"

    file = pg.evaluate("__studio.cur().takes[0].file")
    pg.click(".take [data-approve]")
    pg.wait_for_selector(".badge-game")
    game = TMP_ROOT / f"game-files/Units/orc/peon/{pg.lid}"
    take = TMP_ROOT / f"audio/self-recorded/{CID}/{GID}/{file}"
    dg = ff_tilt(game) - ff_tilt(take)
    assert 8 < dg < 15, f"файл гри: {dg:.1f} дБ"
    m, chain = measure(pg, lambda: pg.click("#playGame"), prefix="game")
    assert chain == [{"kind": "dest"}], chain
    assert 8 < tilt(m) - t0 < 15
    assert not pg.errors, pg.errors


def _band_db(path, lo, hi) -> float:
    af = f"highpass=f={lo},highpass=f={lo},lowpass=f={hi},lowpass=f={hi},volumedetect"
    err = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-af", af, "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    return float(err.split("mean_volume:")[1].split("dB")[0])


def ff_tilt(path) -> float:
    return _band_db(path, 800, 1250) - _band_db(path, 3000, 6000)


# ------------------------------------------------------------------ EQ: живий граф, A/B, чип

def test_bypass_toggle_is_audible_while_playing(eqpage):
    pg = eqpage
    t0 = baseline(pg)
    m1, _ = measure(pg, lambda: pg.click(".take [data-play^='take:']"), ms=400)
    pg.click("#eqBypass")                                              # під час звучання
    pg.wait_for_timeout(260)
    m2 = pg.evaluate("__measure(400)")
    assert tilt(m1) - t0 > 8
    assert abs(tilt(m2) - t0) < 3, f"після «без EQ» нахил {tilt(m2) - t0:.1f} дБ — EQ досі звучить"


def test_profile_switch_is_audible_while_playing(eqpage, svc):
    pg = eqpage
    svc.eq_save(CID, GID, LOWPASS, assign=False)
    pg.evaluate("__studio.eqLoad()")
    pg.wait_for_function("() => __studio.EQ.data.profiles.some((p) => p.name === 'Тест зріз 500 Гц')")
    lp = pg.evaluate("__studio.EQ.data.profiles.find((p) => p.name === 'Тест зріз 500 Гц').id")
    pg.click("#eqPanel summary")
    measure(pg, lambda: pg.click(".take [data-play^='take:']"), ms=200)
    pg.select_option("#eqSel", lp)
    pg.wait_for_function(f"() => __studio.EQ.id === '{lp}'")
    assert [n["type"] for n in pg.evaluate("__chain()") if n["kind"] == "biquad"] == ["lowpass"]


def test_eq_applied_before_eq_api_answers(eqpage):
    pg = eqpage
    pg.route("**/api/eq?*", lambda r: (pg.wait_for_timeout(1500), r.continue_()))
    pg.reload()
    pg.wait_for_selector(".take [data-play^='take:']")
    pg.evaluate("document.activeElement.blur()")
    pg.keyboard.press("KeyL")
    pg.wait_for_function("() => __studio.playing && __studio.playing.id.startsWith('take:')", timeout=5000)
    assert has_boost(pg.evaluate("__chain()")), pg.evaluate("__chain()")


def test_playing_take_shows_eq_chip(eqpage):
    pg = eqpage
    measure(pg, lambda: pg.click(".take [data-play^='take:']"), ms=300)
    chip = pg.locator(".take [data-eq-chip]")
    assert chip.count() >= 1 and "Тест +12" in chip.first.inner_text()


def test_shortcuts_work_with_focus_on_eq_slider(eqpage):
    """L/A/B проходять із повзунка EQ; стрілки лишаються повзунку (значення змінюється, репліка — ні)."""
    pg = eqpage
    pg.click("#eqPanel summary")
    sl = pg.locator("input[data-eq='gain'][data-i='0']")
    sl.focus()
    idx, v0 = pg.evaluate("__studio.S.idx"), sl.input_value()
    pg.keyboard.press("ArrowLeft")
    assert sl.input_value() != v0 and pg.evaluate("__studio.S.idx") == idx
    pg.keyboard.press("KeyL")
    pg.wait_for_function("() => __studio.playing && __studio.playing.id.startsWith('take:')", timeout=8000)
    pg.keyboard.press("KeyA")                                          # A/B без зупинки
    pg.wait_for_function("() => __studio.EQ.bypass")
    assert pg.evaluate("!!__studio.playing")
    assert "on" not in (pg.locator("[data-eq-chip]").get_attribute("class") or "").split()
    pg.locator("[data-eq-chip]").click()                               # клік по чипу — назад
    pg.wait_for_function("() => !__studio.EQ.bypass")
    assert pg.get_attribute("#eqBypass", "aria-pressed") == "false"
    assert not pg.errors, pg.errors


def test_ab_loudness_matched(eqpage):
    """«Без EQ» (B) вирівняно за RMS із «З EQ» (A): різниця на виході ≤ 1 дБ."""
    pg = eqpage
    pg.evaluate("""() => { window.__rms = async (ms = 500) => { const an = window.__tap, b = new Float32Array(an.fftSize);
      let s = 0, n = 0; const t0 = performance.now();
      while (performance.now() - t0 < ms) { an.getFloatTimeDomainData(b); for (const v of b) { s += v * v; n++; } await new Promise((r) => setTimeout(r, 30)); }
      return 20 * Math.log10(Math.sqrt(s / n)); }; }""")
    measure(pg, lambda: pg.click(".take [data-play^='take:']"), ms=600)
    a = pg.evaluate("__rms(500)")
    pg.keyboard.press("KeyA")
    pg.wait_for_function("() => __studio.EQ.bypass")
    pg.wait_for_timeout(300)
    b = pg.evaluate("__rms(500)")
    assert abs(a - b) < 1.0, (a, b)
    assert not pg.errors, pg.errors


def test_shelf_has_no_q_control(eqpage, svc):
    pg = eqpage
    shelf = {"name": "Полиця", "enabled": True, "gain_db": 0,
             "bands": [{"type": "lowshelf", "freq_hz": 150, "gain_db": 3, "q": 0.71}]}
    svc.eq_save(CID, GID, shelf)
    pg.evaluate("__studio.eqLoad()")
    pg.click("#eqPanel summary")
    pg.wait_for_selector("input[data-eq='freq']")
    assert pg.locator("input[data-eq='q']").count() == 0


# ------------------------------------------------------------------ бічна панель: список реплік не зникає

def _open_side_panels(pg, w, h):
    pg.set_viewport_size({"width": w, "height": h})
    for sel in ("#character", "#eqPanel"):
        if not pg.evaluate(f"document.querySelector('{sel}').open"):
            pg.click(f"{sel} > summary")
    pg.wait_for_selector("#eqCurve")


SIDE = """() => { const c = document.querySelector('#cues'), f = document.querySelector('#filter'),
  on = c.querySelector('.cue.on'), vh = innerHeight, r = (e) => e.getBoundingClientRect();
  const inView = (e) => { const b = r(e); return b.top >= 0 && b.bottom <= vh; };
  const cr = r(c), o = r(on);
  return { cuesH: c.clientHeight, filterInView: inView(f), onInView: inView(on) && o.top >= cr.top - 1 && o.bottom <= cr.bottom + 1 }; }"""


@pytest.mark.parametrize("w,h", [(1440, 900), (1280, 800)])
def test_cue_list_stays_scrollable_with_panels_open(page, w, h):  # noqa: F811
    pg = page
    _open_side_panels(pg, w, h)
    s = pg.evaluate(SIDE)
    assert s["cuesH"] >= 200, s                                         # видно щонайменше ~3 репліки
    assert s["filterInView"], s                                         # фільтр досяжний без прокрутки панелі
    pg.evaluate("document.activeElement.blur()")
    for _ in range(10):
        pg.keyboard.press("ArrowDown")
    pg.wait_for_timeout(200)
    s = pg.evaluate(SIDE)
    assert s["onInView"], s                                             # ↑/↓ тримає активну репліку на екрані


def test_cue_list_scrollable_with_panels_closed(page):  # noqa: F811
    """Контроль: без розгорнутих панелей усе гаразд (регресія має лишитися відловленою вище)."""
    pg = page
    pg.set_viewport_size({"width": 1280, "height": 800})
    pg.evaluate("document.activeElement.blur()")
    for _ in range(12):
        pg.keyboard.press("ArrowDown")
    pg.wait_for_timeout(200)
    s = pg.evaluate(SIDE)
    assert s["cuesH"] >= 200 and s["filterInView"] and s["onInView"], s
