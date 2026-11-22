"""e2e «ШІ-чернетка юніта / раси» в Chrome: прогрес «живі / ШІ / оригінал» у шапці, бічній панелі й меню юнітів, діалог,
та сама згода «це мій голос», «одразу обрати як чернетку», скасування всієї чернетки з індикатора черги. Двигуни фейкові."""
import threading

from aistudio import config
from test_aistudio import FakeEngine
from test_studio_e2e import page  # noqa: F401  (фікстура Chrome-сторінки)
from test_studio_e2e_ai import ai_env, consented, open_panel  # noqa: F401  (фейкові двигуни + 2 обрані власні дублі peon)


def test_draft_unit_consent_approve_and_progress(ai_env, page):  # noqa: F811
    pg = page
    assert "живі 2 · ШІ 0 · ориг. 16" in pg.inner_text("#unitMix") and "живі 2" in pg.inner_text("#draftBar")
    open_panel(pg)                                                                    # поточний двигун — фейковий
    pg.click("#draftBtn")
    pg.wait_for_selector("#draftModal [data-draft-go]")
    assert "Юніт" in pg.inner_text("#draftModal .draft-scope") and pg.is_checked("#draftApprove")
    assert "6 реплік" in pg.inner_text("#draftModal [data-scope=unit]") and "Оцінка" in pg.inner_text("#draftEta")
    pg.click("#draftModal [data-draft-go]")
    pg.wait_for_selector("#aiConsent input[data-c=own]")                              # та сама згода, що й у генерації
    pg.click("#aiConsent [data-c-cancel]")
    assert not ai_env.jobs() and pg.is_visible("#draftModal")
    pg.click("#draftModal [data-draft-go]")
    pg.check("#aiConsent input[data-c=own]")
    pg.click("#aiConsent [data-c-ok]")
    pg.wait_for_selector("#toast >> text=ШІ-чернетка: у черзі 6 реплік")
    assert config.has_consent() and pg.locator("#draftModal").count() == 0
    pg.wait_for_selector("#toast >> text=ШІ-чернетка готова: 6 з 6", timeout=30000)
    pg.wait_for_function("document.querySelector('#unitMix').textContent.includes('ШІ 6')")
    assert all(j["draft"]["approve"] and j["state"] == "done" for j in ai_env.jobs())
    pg.wait_for_selector(".approved-banner")                                          # поточна репліка: ШІ-дубль обрано для гри
    assert pg.locator(".take.approved .badge-ai").count() == 1
    assert "ШІ 6" in pg.inner_text("#draftBar") and "6 з 6" not in pg.inner_text("#unitSub")
    pg.click("#unitBtn")
    pg.wait_for_selector(".race-draft")
    assert "ШІ 6" in pg.inner_text(".race-draft") and "живі 2" in pg.inner_text(".unit-card.on .mix-t")
    pg.click("[data-draft-race]")                                                     # раса: решта юнітів без тексту — нічого ставити
    pg.wait_for_selector("#draftModal [data-draft-go]")
    assert pg.is_disabled("#draftModal [data-draft-go]") and "нічого ставити" in pg.inner_text("#draftEta")
    assert pg.locator("#draftModal [data-scope=unit]").count() == 1
    pg.click("#draftModal [data-draft-close]")
    assert pg.locator("#draftModal").count() == 0 and not [e for e in pg.errors if "/api/install/plan" not in e]


def test_draft_cancel_all_from_queue(consented, page):  # noqa: F811
    ai = consented
    FakeEngine.block = threading.Event()
    pg = page
    open_panel(pg)
    pg.click("#draftBtn")
    pg.wait_for_selector("#draftModal [data-draft-go]")
    pg.uncheck("#draftApprove")
    assert pg.evaluate("localStorage.getItem('studio.draftApprove')") == "0"
    pg.click("#draftModal [data-scope=race]")
    assert pg.locator("#draftModal [data-scope=race].on").count() == 1
    pg.click("#draftModal [data-draft-go]")
    pg.wait_for_selector("#toast >> text=у черзі 6 реплік")
    pg.wait_for_selector("#aiQueue:not([hidden])")
    pg.click("#aiQueueBtn")
    pg.wait_for_selector("[data-draft-cancel]")
    assert "чернетка ·" in pg.inner_text("#aiQueuePop") and "· 6" in pg.inner_text("[data-draft-cancel]")
    pg.click("#draftBtn")                                                             # у діалозі видно, що вже в черзі
    pg.wait_for_selector("[data-draft-stop]")
    pg.click("[data-draft-stop]")
    pg.wait_for_selector("#toast >> text=Скасовано завдань чернетки: 6")
    pg.wait_for_selector("#aiQueue", state="hidden", timeout=15000)
    assert {j["state"] for j in ai.jobs()} == {"cancelled"} and not any(j["draft"]["approve"] for j in ai.jobs())
    assert "ШІ 0" in pg.inner_text("#unitMix")
