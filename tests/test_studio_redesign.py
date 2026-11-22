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
    pg.click("#eqPanel summary")
    assert pg.locator(".stale-chip").count() == 0 and pg.inner_text("#eqReexport").strip() == "Оновити файли гри"
    pg.select_option("#eqSel", "orc-tauren")                    # інший профіль → файл у грі відстав
    pg.wait_for_selector(".stale-chip")
    assert "(1)" in pg.inner_text("#eqReexport")
    assert "Файл у грі" in pg.inner_text("#playGame")
    pg.click("#eqReexport")
    pg.wait_for_function("() => !document.querySelector('.stale-chip')")
    assert "(" not in pg.inner_text("#eqReexport")
    assert not pg.errors, pg.errors
