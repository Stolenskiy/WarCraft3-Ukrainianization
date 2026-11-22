"""Chrome: панель «Персонаж» у вкладці «Обробка» — пропозиція з voice bible, повзунки, ввімкнення, A/B «з пресетом / без»
(друге джерело з /api/character/audio), «Оновити файли гри» записує пресет у файл гри, «Скинути до voice bible»."""
import pytest

pytest.importorskip("playwright.sync_api")

from conftest import synth  # noqa: E402
from test_studio_core import _read_game, _zcr_hz  # noqa: E402
from test_studio_e2e import page  # noqa: E402,F401  (фікстура Chrome + фейковий мікрофон)

CID, GID = "units-orc", "peon"


@pytest.fixture
def chpage(page, svc, tmp_path):  # noqa: F811
    """Поточна репліка з обраним дублем (тон 440 Гц) — файл гри вже є, пресет ще вимкнений."""
    pg = page
    lid = pg.evaluate("__studio.cur().id")
    f = svc.add_take(CID, GID, lid, synth(tmp_path / "t.wav", 1.2, 440).read_bytes())["takes"][-1]["file"]
    svc.approve(CID, GID, lid, f)
    i = pg.evaluate("__studio.S.idx")
    pg.reload()
    pg.wait_for_selector(".cue.on")
    pg.click(f".cue[data-i='{i}']")                                                # обрана репліка вже «готова» — відкрити її
    pg.wait_for_selector(".take [data-play^='take:']")
    pg.click("#tabProc")
    pg.wait_for_selector("input[data-ch='pitch_st']")
    pg.lid = lid
    return pg


def set_range(pg, key, value):
    with pg.expect_response(lambda r: r.url.endswith("/api/character") and r.request.method == "POST"):
        pg.eval_on_selector(f"input[data-ch='{key}']", "(el, v) => { el.value = v; el.dispatchEvent(new Event('input', {bubbles: true})); }", value)


def test_character_panel_ab_and_game_file(chpage, svc):
    pg = chpage
    box = pg.inner_text("#char")
    assert "Персонаж" in box and "раса: нижче" in box and "гроул: хрип" in box     # пропозиція з voice bible (фікстура)
    assert "немає рядка «Обробка»" in box and pg.locator("#charReset").count() == 0
    assert not pg.is_checked("#charOn") and pg.inner_text("#eqA") == "A · з EQ"
    assert pg.input_value("input[data-ch='formant_pct']") == "-10"

    with pg.expect_response(lambda r: r.url.endswith("/api/character") and r.request.method == "POST"):
        pg.click("label:has(#charOn)")
    set_range(pg, "pitch_st", "5")
    pg.wait_for_selector("#charReset")
    assert "+5 пт" in pg.inner_text("#char") and pg.inner_text("#eqA") == "A · з пресетом"
    assert svc.character(CID, GID)["enabled"] is True and svc.character(CID, GID)["pitch_st"] == 5
    pg.wait_for_selector("#eqReexport >> text=(1)")                                # файл гри відстав від пресета

    with pg.expect_response(lambda r: "/api/character/audio?" in r.url and r.status == 200):
        pg.click(".take [data-play^='take:']")
    pg.wait_for_function("() => __studio.EQ.live && __studio.EQ.live.wsrc !== __studio.EQ.live.src")
    assert "Персонаж · EQ" in pg.inner_text("[data-eq-chip]")
    pg.click("#eqB")                                                               # B: сирий дубль, A вимкнено
    pg.wait_for_function("() => __studio.EQ.live && __studio.EQ.live.wet.gain.value < 0.05 && __studio.EQ.live.dry.gain.value > 0.2")
    pg.click("#eqA")
    pg.wait_for_function("() => __studio.EQ.live && __studio.EQ.live.wet.gain.value > 0.9 && __studio.EQ.live.dry.gain.value < 0.05")
    pg.evaluate("__studio.stopPlay()")

    before = _zcr_hz(_read_game()[1][3000:12000])
    pg.click("#eqReexport")
    pg.wait_for_selector("#toast >> text=EQ застосовано")
    assert abs(before - 440) < 20 and abs(_zcr_hz(_read_game()[1][3000:12000]) - 440 * 2 ** (5 / 12)) < 25

    pg.reload()                                                                    # стан пресета — на сервері
    pg.wait_for_selector(".cue.on")
    pg.click("#tabProc")
    pg.wait_for_selector("#charReset")
    assert pg.is_checked("#charOn") and pg.input_value("input[data-ch='pitch_st']") == "5"
    pg.click("#charReset")
    pg.wait_for_selector("#toast >> text=скинуто")
    assert pg.locator("#charReset").count() == 0 and not pg.is_checked("#charOn")
    assert pg.inner_text("#eqA") == "A · з EQ" and svc.character(CID, GID)["enabled"] is False
    pg.wait_for_selector("#eqReexport >> text=(1)")
    assert not pg.errors, pg.errors


def test_disabled_preset_keeps_single_source(chpage):
    pg = chpage
    pg.click(".take [data-play^='take:']")
    pg.wait_for_function("() => __studio.EQ.live")
    assert pg.evaluate("__studio.EQ.live.wsrc === __studio.EQ.live.src")
    pg.focus("input[data-ch='drive']")                                             # на повзунку A перемикає A/B, R — ні
    pg.keyboard.press("KeyA")
    assert pg.evaluate("__studio.EQ.bypass") is True
    pg.keyboard.press("KeyR")
    assert pg.evaluate("__studio.playing && __studio.playing.id") != "ref"
    assert not pg.errors, pg.errors
