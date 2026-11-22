"""Редизайн студії (вкладки, EQ-редактор, голосова картка, шапка) — перевірки у справжньому Chrome."""
import pytest

pytest.importorskip("playwright.sync_api")

from test_studio_core import wav_bytes  # noqa: E402,F401
from test_studio_e2e import page  # noqa: E402,F401  (фікстура Chrome)

CID, GID = "units-orc", "peon"


def test_stale_counter_after_eq_change_and_reexport_clears(page, svc):  # noqa: F811
    pg = page
    lid = pg.evaluate("__studio.cur().id")
    svc.add_take(CID, GID, lid, wav_bytes())
    svc.approve(CID, GID, lid, f"{svc.line(CID, GID, lid).stem}.take1.wav")
    pg.reload()
    pg.click(".cue >> nth=0")                                   # після перезавантаження студія стрибає до першої незатвердженої
    pg.wait_for_selector(".approved-banner")
    pg.click("#tabProc")
    assert pg.locator(".stale-chip").count() == 0 and pg.inner_text("#eqReexport").strip() == "Оновити файли гри"
    pg.select_option("#eqSel", "orc-tauren")                    # інший профіль → файл у грі відстав
    pg.wait_for_selector(".stale-chip")
    assert "(1)" in pg.inner_text("#eqReexport")
    assert "Файл у грі" in pg.inner_text("#playGame")
    pg.click("#eqReexport")
    pg.wait_for_function("() => !document.querySelector('.stale-chip')")
    assert "(" not in pg.inner_text("#eqReexport")
    assert not pg.errors, pg.errors


def test_tabs_keep_their_own_scroll_and_keyboard(page):  # noqa: F811
    pg = page
    pg.set_viewport_size({"width": 1280, "height": 500})
    pg.evaluate("document.querySelector('#cues').scrollTop = 40")
    top = pg.evaluate("document.querySelector('#cues').scrollTop")
    pg.click("#tabProc")
    assert pg.get_attribute("#tabProc", "aria-selected") == "true" and pg.is_visible("#eq")
    assert not pg.is_visible("#cues")                           # неактивна вкладка не видна й не фокусується
    pg.evaluate("document.querySelector('#paneProc').scrollTop = 30")
    pg.click("#tabCues")
    assert pg.evaluate("document.querySelector('#cues').scrollTop") == top
    pg.click("#tabProc")
    assert pg.evaluate("document.querySelector('#paneProc').scrollTop") > 0
    pg.focus("#tabProc")                                         # ←/→ перемикають вкладки, ↑/↓ лишаються за репліками
    pg.keyboard.press("ArrowLeft")
    assert pg.get_attribute("#tabCues", "aria-selected") == "true"
    idx = pg.evaluate("__studio.S.idx")
    pg.keyboard.press("ArrowDown")
    assert pg.evaluate("__studio.S.idx") == idx + 1
    assert not pg.errors, pg.errors
