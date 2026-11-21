"""Дрейф документації: маршрути сервера ↔ docstring і README студії, AGENTS.md ↔ Makefile і файли, ліміти розміру."""
import ast
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SERVER = REPO / "tools/studio/server.py"
AGENTS = (REPO / "AGENTS.md").read_text(encoding="utf-8")
PATH_RE = re.compile(r"`((?:docs|tools|tests|\.github|\.claude|\.githooks)/[^`\s→«»<>]*)`")


def server_routes() -> set[str]:
    """Усі маршрути з коду server.py (рядки "/api/…", порівняння parts == ["api", …], parts[:2] == ["audio", …])."""
    tree = ast.parse(SERVER.read_text(encoding="utf-8"))
    doc = ast.get_docstring(tree, clean=False)
    routes: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value != doc:
            if re.fullmatch(r"/(api|audio)/[\w/-]+", n.value):
                routes.add(n.value.rstrip("/"))
        if isinstance(n, ast.Compare) and isinstance(n.comparators[0], ast.List):
            parts = [e.value for e in n.comparators[0].elts if isinstance(e, ast.Constant)]
            if parts and parts[0] in ("api", "audio") and len(parts) > 1:
                routes.add("/" + "/".join(parts))
    return routes


def test_routes_are_found():
    r = server_routes()
    assert {"/api/take", "/api/approve", "/api/catalogs", "/api/install/plan", "/api/group", "/audio/voice"} <= r


@pytest.mark.parametrize("where", ["docstring", "readme"])
def test_every_route_documented(where):
    tree = ast.parse(SERVER.read_text(encoding="utf-8"))
    text = ast.get_docstring(tree, clean=False) if where == "docstring" else (REPO / "tools/studio/README.md").read_text(encoding="utf-8")
    missing = sorted(r for r in server_routes() if r not in text)
    assert not missing, f"маршрути без опису ({where}): {missing} — додайте в docstring server.py і tools/studio/README.md"


def makefile_targets() -> set[str]:
    return set(re.findall(r"^([a-z][\w-]*):", (REPO / "Makefile").read_text(encoding="utf-8"), re.M))


def test_agents_make_targets_exist():
    used = set(re.findall(r"`make ([a-z][\w-]*)", AGENTS))
    assert {"verify", "check", "doctor", "setup-dev"} <= used
    assert not used - makefile_targets(), f"AGENTS.md згадує неіснуючі цілі: {sorted(used - makefile_targets())}"


def test_agents_paths_exist():
    paths = set(PATH_RE.findall(AGENTS))
    assert len(paths) >= 12
    bad = sorted(p for p in paths if not (REPO / p).exists() and not list(REPO.glob(p)))
    assert not bad, f"AGENTS.md посилається на неіснуючі шляхи: {bad}"


def test_claude_md_imports_agents():
    assert (REPO / "CLAUDE.md").read_text(encoding="utf-8").lstrip().startswith("@AGENTS.md")


def test_skills_point_to_existing_docs_and_stay_thin():
    for sk in sorted((REPO / ".claude/skills").glob("*/SKILL.md")):
        text = sk.read_text(encoding="utf-8")
        assert len(text.splitlines()) <= 40, f"{sk}: скіл має бути ≤ 40 рядків"
        assert re.search(r"^description: Use (when|before)", text, re.M), f"{sk}: опис має починатися з «Use when/before»"
        for p in re.findall(r"`(docs/[^`\s]+\.md)`", text):
            assert (REPO / p).exists(), f"{sk}: немає {p}"


@pytest.mark.parametrize(("path", "limit"), [("AGENTS.md", 80), ("docs/STATUS.md", 40)])
def test_size_budgets(path, limit):
    assert len((REPO / path).read_text(encoding="utf-8").splitlines()) <= limit


def test_adrs_are_short():
    adrs = sorted((REPO / "docs/decisions").glob("0*.md"))
    assert len(adrs) >= 5
    for a in adrs:
        assert len(a.read_text(encoding="utf-8").splitlines()) <= 25, a.name
