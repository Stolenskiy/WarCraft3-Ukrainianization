"""e2e ШІ-очищення в Chrome: «✨ Очистити» на дублі → новий дубль «очищено ← N» з «Було → стало»; масове очищення в «Обробка»;
встановлення однією кнопкою, після якого відкладене очищення стартує саме. Модель — фейковий робітник (tests/test_enhance.py)."""
import pytest
from aistudio import enhance, eta
from aistudio.enhance_jobs import EnhanceQueue
from conftest import TMP_ROOT, synth
from test_enhance import FakeRunner
from test_studio_e2e import page  # noqa: F401  (фікстура Chrome-сторінки)

CID, GID = "units-orc", "peon"


def _install(model):
    for name, size in enhance.MODEL_FILES.items():
        (model / name).parent.mkdir(parents=True, exist_ok=True)
        with open(model / name, "wb") as f:
            f.truncate(size)


@pytest.fixture
def world(svc, tmp_path, monkeypatch):
    py, model = tmp_path / "venv/bin/python", tmp_path / "model"
    monkeypatch.setenv("WC3_ENHANCE_PY", str(py))
    monkeypatch.setenv("WC3_ENHANCE_MODEL", str(model))
    FakeRunner.fail, FakeRunner.block, FakeRunner.seen = set(), None, []

    def setup(say):
        say("ставлю залежності")
        py.parent.mkdir(parents=True, exist_ok=True)
        py.write_text("")
        _install(model)

    svc._enhance = EnhanceQueue(svc, eta.Timing(tmp_path / "t.json"), runner_factory=FakeRunner, setup_fn=setup)
    for lid in ("peonyes1.wav", "peonyes2.wav"):
        f = svc.add_take(CID, GID, lid, synth(TMP_ROOT / "own.wav", 0.9).read_bytes())["takes"][-1]["file"]
        svc.approve(CID, GID, lid, f)
    return py, model, setup


@pytest.fixture
def installed(world):
    world[2](lambda _: None)
    return world


def test_clean_one_take_then_bulk_from_processing_tab(installed, page):  # noqa: F811
    pg = page
    pg.click(".cue >> text=Сделаю.")                                                       # peonyes1: обраний власний дубль
    pg.wait_for_selector(".take [data-enhance]")
    pg.click(".take [data-enhance]")
    pg.wait_for_selector(".take .badge-enh", timeout=15000)
    assert "очищено ← 1" in pg.inner_text(".take .badge-enh")
    assert pg.locator(".take [data-ab-enh]").count() == 1 and pg.locator(".take.approved [data-enhance]").count() == 1   # обраний — той самий
    pg.click("#tabProc")
    pg.wait_for_selector("#enhAppr")
    assert "· 1" in pg.inner_text("#enhAppr") and pg.is_checked("#enhApprove")          # peonyes1 уже очищено, лишився peonyes2
    assert "MIT" in pg.inner_text("#enhBox")
    pg.click("#enhAppr")
    pg.wait_for_selector("#toast >> text=у гру: 1", timeout=15000)
    pg.wait_for_function("document.querySelector('#enhAppr').textContent.includes('· 0')")
    assert svc_take_sources(installed) and not [e for e in pg.errors if "/api/install/plan" not in e]


def svc_take_sources(installed):
    import json
    st = json.loads((TMP_ROOT / f"data/studio/{CID}.json").read_text())
    e = st[GID]["peonyes2.wav"] if GID in st else st["groups"][GID]["peonyes2.wav"]
    appr = next(t for t in e["takes"] if t["file"] == e["approved"])
    return appr.get("source") == "enhanced"


def test_install_button_then_pending_clean_runs(world, page):  # noqa: F811
    pg = page
    pg.click(".cue >> text=Сделаю.")                                                       # peonyes1: обраний власний дубль
    pg.wait_for_selector(".take [data-enhance]")
    pg.click(".take [data-enhance]")
    pg.wait_for_selector("#enhSetup")                                                      # не встановлено → вкладка «Обробка»
    assert pg.get_attribute("#tabProc", "aria-selected") == "true" and "≈ 290 МБ" in pg.inner_text("#enhSetup")
    pg.click("#enhSetup")
    pg.wait_for_selector("#toast >> text=ШІ-очищення встановлено", timeout=15000)
    pg.wait_for_selector("#enhAppr", timeout=15000)
    pg.click("#tabCues")
    pg.wait_for_selector(".take .badge-enh", timeout=15000)                              # відкладене очищення стартувало саме
