"""e2e (Chrome): автотривалість і автовибір ШІ-варіантів — бейджі оцінки/«найкращий»/«не влазить», «★ Обрати найкращий для гри»,
«Взяти в дублі» з темпом під оригінал, пріоритет живого дубля, «Обирати найкращий автоматично» після генерації (фейковий двигун)."""
from conftest import TMP_ROOT, synth
from studio import ai
from test_studio_e2e import page  # noqa: F401  (фікстура Chrome-сторінки)
from test_studio_e2e_ai import ai_env, consented, open_panel  # noqa: F401  (фейкові двигуни, згода)

CID, GID, LID = "units-orc", "peon", "peonyes1.wav"
AI_DIR = TMP_ROOT / "audio/ai" / CID / GID


def variant(k, sec, cer):
    w = synth(AI_DIR / f"peonyes1.ai{k}.wav", sec, 300 + 20 * k)
    ai.write_sidecar(w, {"ai": True, "engine": "fish-s2-pro", "model": "m", "seed": k, "temperature": 0.7, "style": None,
                         "ref_takes": [], "text": "Зроблю.", "cer": cer, "similarity": 0.9, "dur": sec,
                         "created": "2026-11-22T10:00:00", "peak_db": -3.0, "clipped": False})


def test_rank_badges_pick_best_fit_and_live_priority(svc, page):  # noqa: F811
    variant(1, 0.8, 0.3)
    variant(2, 0.8, 0.0)                                       # найкращий
    variant(3, 1.3, 0.0)                                       # задовгий: ×1.6 > ×1.25
    pg = page
    pg.reload()
    pg.wait_for_selector("#aiSection .ai-take")
    assert pg.locator("#aiSection .ai-best").count() == 1
    assert "найкращий" in pg.inner_text("[data-ai-row='peonyes1.ai2.wav']")
    bad = pg.locator("[data-ai-row='peonyes1.ai3.wav'] .ai-fit.bad")
    assert "не влазить" in bad.inner_text() and "Скоротіть" in bad.get_attribute("title")
    assert "№1" in pg.inner_text("[data-ai-row='peonyes1.ai2.wav'] .ai-score")
    assert pg.is_checked("[data-ai-fit]") and not pg.is_checked("[data-ai-autopick]")
    pg.click("[data-ai-pick]")                                 # ★ найкращий → дубль «ШІ» → у гру
    pg.wait_for_selector("#toast >> text=У грі — ШІ-варіант 2")
    pg.wait_for_selector(".approved-banner")
    e = svc.store(CID).entry(GID, LID)
    t = next(x for x in e["takes"] if x["file"] == e["approved"])
    assert t["source"] == "ai" and t["ai_file"] == "peonyes1.ai2.wav"
    pg.click("[data-ai-row='peonyes1.ai3.wav'] [data-ai-adopt]")    # автотривалість: темп ×1.25 (межа)
    pg.wait_for_selector("#toast >> text=темп ×1.25 під оригінал")
    assert svc.store(CID).entry(GID, LID)["takes"][-1]["tempo"] == 1.25
    pg.uncheck("[data-ai-fit]")                                # вимкнено → без темпу (пам'ятається в браузері)
    assert pg.evaluate("localStorage.getItem('studio.aiFit')") == "0"
    pg.click("[data-ai-row='peonyes1.ai1.wav'] [data-ai-adopt]")
    pg.wait_for_function("document.querySelectorAll('#aiSection .ai-take.adopted').length === 3")
    assert "tempo" not in svc.store(CID).entry(GID, LID)["takes"][-1]
    f = svc.add_take(CID, GID, LID, synth(TMP_ROOT / "own.wav", 0.9).read_bytes())["takes"][-1]["file"]
    svc.approve(CID, GID, LID, f)                              # живий дубль у грі — автовибір недоступний
    pg.reload()
    pg.wait_for_selector(".cue.on")
    i = pg.evaluate(f"__studio.S.phrases.findIndex((x) => x.id === '{LID}')")   # після перезавантаження — перша незатверджена
    pg.click(f".cue[data-i='{i}']")
    pg.wait_for_selector("[data-ai-pick]")
    assert pg.is_disabled("[data-ai-pick]") and "живий дубль" in pg.inner_text("[data-ai-pick-why]")
    assert not [x for x in pg.errors if "/api/install/plan" not in x]


def test_auto_pick_after_generation(consented, page):  # noqa: F811
    pg = page
    open_panel(pg)
    pg.check("[data-ai-autopick]")
    pg.select_option("#aiN", "2")
    pg.click("[data-ai-go]")
    pg.wait_for_selector("#toast >> text=у грі найкращий", timeout=15000)
    pg.wait_for_selector(".approved-banner", timeout=5000)     # картка оновилась сама
    assert pg.locator("#aiSection .ai-take").count() == 2 and pg.locator("#aiSection .ai-best").count() == 1
    job = consented.jobs()[-1]
    assert job["auto_pick"] and job["pick"]["take"] == consented.svc.store(CID).entry(GID, LID)["approved"]
    assert not [x for x in pg.errors if "/api/install/plan" not in x]
