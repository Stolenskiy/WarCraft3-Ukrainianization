"""e2e ШІ-студії в Chrome: панель «Згенерувати», згода, черга, «На основі цього», вибір двигуна, чекбокс «Текст» у вікні встановлення.
Двигуни фейкові (tests/test_aistudio.py), модель не потрібна; усе в тимчасових теках."""
import threading

import install_pack
import pytest
import textpack
from aistudio import config
from aistudio import engines as E
from aistudio.api import AiStudio
from aistudio.jobs import JobQueue
from conftest import TMP_ROOT, synth
from test_aistudio import FakeCloud, FakeEngine
from test_studio_e2e import page  # noqa: F401  (фікстура Chrome-сторінки)

CID, GID = "units-orc", "peon"


class Asr:
    def transcribe(self, paths):
        return {str(p): "Зроблю." for p in paths}


@pytest.fixture
def ai_env(svc):
    config.settings_path().unlink(missing_ok=True)
    FakeEngine.block, FakeEngine.calls = None, []
    E.register(FakeEngine)
    E.register(FakeCloud)
    for lid in ("peonyes2.wav", "peonyes3.wav"):
        f = svc.add_take(CID, GID, lid, synth(TMP_ROOT / "own.wav", 0.9).read_bytes())["takes"][-1]["file"]
        svc.approve(CID, GID, lid, f)
    svc._aistudio = AiStudio(svc, JobQueue(svc, TMP_ROOT / "audio/ai/.jobs", asr_factory=Asr))
    yield svc._aistudio
    if FakeEngine.block is not None:
        FakeEngine.block.set()
    svc._aistudio.queue.stop()
    E.unregister("fake-local")
    E.unregister("fake-cloud")


@pytest.fixture
def consented(ai_env):
    config.set_consent(True)                  # до відкриття сторінки: статус підтягується при першому показі панелі
    return ai_env


def open_panel(pg, engine="fake-local"):
    pg.click("#aiSection > .ai-gen-host summary")
    pg.wait_for_selector("#aiEngine")
    pg.select_option("#aiEngine", engine)


def test_generate_flow_consent_then_variant_then_based_on(ai_env, page):  # noqa: F811
    pg = page
    open_panel(pg)
    assert pg.locator("#aiText").input_value() == "Зроблю."                          # за замовчуванням — текст репліки
    assert "комерційне: так" in pg.inner_text(".ai-eng-row") and "готово" in pg.inner_text(".ai-eng-row")
    assert pg.locator("#aiRefs input[data-ref]").count() == 2                         # затверджені дублі інших реплік
    pg.click("#aiRefFilter [data-rf=all]")
    pg.fill("#aiText", "Зроблю!!!")
    pg.fill("#aiSeed", "5")
    pg.click("[data-ai-go]")
    pg.wait_for_selector("#aiConsent")                                                # перша генерація заблокована згодою
    assert pg.is_disabled("#aiConsent [data-c-ok]") and not ai_env.jobs()
    pg.click("#aiConsent [data-c-cancel]")
    assert not ai_env.jobs() and not config.has_consent()
    pg.click("[data-ai-go]")
    pg.check("#aiConsent input[data-c=own]")
    pg.click("#aiConsent [data-c-ok]")
    pg.wait_for_selector("#toast >> text=У черзі ШІ")
    assert config.has_consent()
    pg.wait_for_selector("#aiSection .ai-take", timeout=15000)                        # новий варіант з’явився сам
    assert "ШІ · CC BY" in pg.inner_text("#aiSection .badge-ai") and "fake-local" in pg.inner_text(".ai-take .ai-engine")
    pg.wait_for_selector("#toast >> text=ШІ: готово")
    assert "seed 5" in pg.inner_text(".ai-params summary")
    pg.click(".ai-params summary")
    assert '"text_override": "Зроблю!!!"' in pg.inner_text(".ai-params pre")
    pg.fill("#aiText", "інше")                                                        # «На основі цього» перезаписує форму
    pg.fill("#aiSeed", "")
    pg.click("[data-ai-based]")
    pg.wait_for_function("document.querySelector('#aiText').value === 'Зроблю!!!'")
    assert pg.input_value("#aiSeed") == "5" and pg.locator("#aiN").input_value() == "1"
    pg.click(".ai-take [data-ai-again]")                                              # «Ще варіант» з іншим seed
    pg.wait_for_function("document.querySelectorAll('#aiSection .ai-take').length === 2", timeout=15000)
    seeds = {v["seed"] for v in pg.evaluate("window.__studio.cur().ai")}
    assert len(seeds) == 2 and not [e for e in pg.errors if "/api/install/plan" not in e]   # 400 плану голосу: немає дублів — очікувано


def test_cancel_from_queue_indicator(consented, page):  # noqa: F811
    ai_env = consented
    FakeEngine.block = threading.Event()
    pg = page
    open_panel(pg)
    pg.click("[data-ai-more]")                                                        # n=1, новий seed
    pg.wait_for_selector("#aiQueue:not([hidden])")
    assert "ШІ:" in pg.inner_text("#aiQueueTxt")
    pg.wait_for_selector("#aiLineProg:not([hidden]) .aip")                           # прогрес — і в картці репліки
    assert pg.locator("#aiLineProg .aip").count() == 1 and pg.locator("#aiLineProg .aiq-bar.big b").count() == 1
    assert any(x in pg.inner_text("#aiLineProg .aip-left") + pg.inner_text("#aiQueueTxt") for x in ("≈", "ще трохи"))
    pg.click("[data-ai-go]")                                                          # друге завдання — у черзі
    pg.wait_for_function("document.querySelector('#aiQueueTxt').textContent.includes('у черзі')")
    pg.click("#aiQueueBtn")
    assert pg.locator("#aiQueuePop [data-cancel]").count() == 2
    pg.locator("#aiQueuePop [data-cancel]").nth(1).click()
    pg.wait_for_function("document.querySelectorAll('#aiQueuePop [data-cancel]').length === 1")
    pg.click("#aiQueuePop [data-cancel]")                                             # скасувати те, що вже генерується
    pg.wait_for_selector("#aiQueue", state="hidden", timeout=15000)
    assert pg.is_hidden("#aiLineProg")
    assert {j["state"] for j in ai_env.jobs()} == {"cancelled"} and not pg.locator("#aiSection .ai-take").count()
    assert pg.locator("#toast").is_visible()


def test_engine_picker_status_license_and_unsupported(consented, page):  # noqa: F811
    ai_env = consented
    pg = page
    open_panel(pg, "fish-s2-pro")
    row = pg.inner_text(".ai-eng-row")
    assert "NC" in row and "локально" in row and "нема середовища" in row            # справжній Fish: у тимчасовому корені немає ні venv, ні моделі
    assert "ai-setup" in pg.inner_text("[data-ai-fix]") and "Fish Audio Research License" in row
    pg.click("[data-ai-go]")                                                          # не готовий двигун: точна підказка, без запиту
    pg.wait_for_selector("#toast >> text=ai-setup")
    assert not ai_env.jobs()
    pg.select_option("#aiEngine", "fake-cloud")
    row = pg.inner_text(".ai-eng-row")
    assert "хмара" in row and "нема ключа" in row and "$1/хв" in pg.inner_text("#aiEngBox")
    assert pg.is_disabled("#aiVar") and pg.is_disabled("#aiStyle") and pg.is_disabled("#aiSeed")   # двигун не підтримує
    assert "не підтримує" in pg.get_attribute("[data-param=style]", "title")
    assert pg.is_enabled("#aiText")
    pg.fill("#aiKey", "TEST-KEY-1")                                                   # ключ → data/local/settings.json
    pg.click("#aiKeySave")
    pg.wait_for_function("document.querySelector('[data-ai-state]').dataset.aiState === 'ready'")
    assert config.api_key("fake-cloud", "NO_SUCH_ENV") == "TEST-KEY-1"
    assert "TEST-KEY-1" not in pg.content() and "хмара" in pg.inner_text(".ai-eng-row")
    pg.click("[data-ai-go]")                                                          # хмара: окрема згода на вивантаження
    pg.wait_for_selector("#aiConsent input[data-c=up]")
    assert pg.locator("#aiConsent input[data-c=own]").count() == 0
    pg.check("#aiConsent input[data-c=up]")
    pg.click("#aiConsent [data-c-ok]")
    pg.wait_for_selector("#toast >> text=У черзі ШІ")
    assert config.upload_consent("fake-cloud")
    pg.wait_for_selector("#aiSection .ai-take", timeout=15000)


def test_install_modal_text_checkbox_dry_run(page, tmp_path, monkeypatch):  # noqa: F811
    game = tmp_path / "wc3"
    (game / "Data").mkdir(parents=True)
    monkeypatch.setenv("WC3_GAME_ROOT", str(game))
    src = tmp_path / "src"
    for rel in ("Units/OrcUnitStrings.txt", "UI/FrameDef.fdf"):
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text("[opeo]\nName=Піон\n", encoding="utf-8")
    res = textpack.BuildResult(files={r: src / r for r in ("Units/OrcUnitStrings.txt", "UI/FrameDef.fdf")},
                               stats={"hotkeys": {"markers_added": 42, "tips_changed": 9, "sections_changed": 4}},
                               source={"commit": "abcdef0123456789" * 2, "variant": "light", "archive_sha256": "c" * 64})
    monkeypatch.setattr(install_pack, "prepare", lambda tid, full=False, ref=None, game=None, log=print, **k: (
        textpack.load_target(tid), game, install_pack.target_root(textpack.load_target(tid), game), res))
    pg = page
    pg.click("#installBtn")
    pg.wait_for_selector("#installParts:not([hidden])")
    assert not pg.is_checked("#partText") and pg.is_checked("#partVoice")
    pg.uncheck("#partVoice")                                                          # лише текст
    pg.check("#partText")
    pg.wait_for_selector("#txTarget")
    assert pg.input_value("#txTarget") == "classic-1.31" and "визначено" in pg.inner_text("#installText")
    assert pg.is_disabled("#installGo") and "план тексту" in pg.get_attribute("#installGo", "title")   # без плану запис заблоковано
    pg.click("#txPlan")
    pg.wait_for_selector(".inst-sum")
    sm = pg.inner_text(".inst-sum")
    assert "abcdef0123" in sm and "нових 2" in sm and "маркерів додано 42" in sm and str(game) in sm
    assert not (game / "Units").exists()                                              # сухий прогін нічого не записав
    assert pg.is_enabled("#installGo") and "Встановити текст" in pg.inner_text("#installGo")
    pg.click("#installGo")
    pg.wait_for_selector("#toast >> text=Текст: встановлено файлів 2")
    assert (game / "Units/OrcUnitStrings.txt").is_file() and (game / "Backups/ua-text/manifest.json").is_file()
    pg.click("#installBtn")                                                           # відкат лишається доступним
    pg.click("#installMode button[data-mode=uninstall]")
    pg.wait_for_selector("[data-tx-un]")
    assert "файлів 2" in pg.inner_text("#installText")
    pg.click("[data-tx-un]")
    pg.wait_for_selector("#toast >> text=Текст прибрано: файлів 2")
    assert not (game / "Units/OrcUnitStrings.txt").exists() and not [e for e in pg.errors if "/api/install/plan" not in e]   # 400 плану голосу: немає дублів — очікувано
