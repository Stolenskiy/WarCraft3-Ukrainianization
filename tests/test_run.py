"""tools/run.py: диспатч команд (subprocess замінено), venv bin/Scripts, паритет із Makefile."""
import re
import sys
from pathlib import Path

import gameconf
import pytest
import run

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture
def calls(monkeypatch):
    log = []

    class R:
        returncode = 0

    monkeypatch.setattr(run.subprocess, "run", lambda cmd, **k: (log.append(list(cmd)), R())[1])
    monkeypatch.setattr(run.subprocess, "Popen", lambda cmd, **k: (log.append(list(cmd)), type("P", (), {"wait": lambda s: 0})())[1])
    monkeypatch.setattr(run.shutil, "which", lambda c: f"/x/{c}")
    return log


def tail(cmd):
    return [Path(x).name if i == 0 else x for i, x in enumerate(cmd)]


def test_venv_python_per_os(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    assert run.venv_python().parts[-2:] == ("Scripts", "python.exe")
    monkeypatch.setattr(sys, "platform", "darwin")
    assert run.venv_python().parts[-2:] == ("bin", "python")


@pytest.mark.parametrize(("argv", "expect"), [
    (["studio"], ["tools/record_studio.py"]),
    (["studio", "--port", "9000", "--no-browser"], ["tools/record_studio.py", "--port", "9000", "--no-browser"]),
    (["install-voices"], ["tools/install_voices.py"]),
    (["install-voices", "--apply"], ["tools/install_voices.py", "--apply"]),
    (["uninstall-voices"], ["tools/install_voices.py", "--uninstall"]),
    (["publish-voice", "--author", "ivan", "--consent"], ["tools/voices.py", "publish", "--author", "ivan", "--consent"]),
    (["check-voices"], ["tools/check_voices.py"]),
    (["transcripts-local"], ["tools/split_transcripts.py"]),
    (["refs"], ["tools/build_refs.py"]),
])
def test_script_commands(calls, argv, expect):
    assert run.main(argv) == 0
    cmd = calls[-1]
    assert cmd[1:4] == ["-I", "-X", "utf8"] and cmd[4:] == expect


def test_doctor_uses_current_python(calls):
    run.main(["doctor"])
    assert calls[-1] == [sys.executable, "-I", "-X", "utf8", "tools/doctor.py"]


def test_publish_requires_author(calls, capsys):
    assert run.main(["publish-voice"]) == 2 and not calls


def test_verify_runs_lint_guard_voices_then_parallel_tests(calls):
    assert run.main(["verify"]) == 0
    flat = [" ".join(c) for c in calls]
    assert any("-m ruff check ." in c for c in flat)
    assert sum("jscheck.mjs" in c for c in flat) == 1
    assert any("guard_no_audio" in c for c in flat) and any("check_voices" in c for c in flat)
    tests = [c for c in calls if "pytest" in c]
    assert len(tests) == 3 and all("--cov" not in c for c in tests)


def test_check_includes_coverage(calls):
    run.main(["check"])
    assert any("--cov" in c for c in calls[-1:]) and "pytest" in calls[-1]


def test_failure_stops_steps(monkeypatch):
    seen = []

    class R:
        returncode = 3

    monkeypatch.setattr(run.subprocess, "run", lambda cmd, **k: (seen.append(cmd), R())[1])
    assert run.main(["check"]) == 3 and len(seen) == 1


def test_env_forces_utf8():
    assert run.child_env()["PYTHONUTF8"]


def test_docker(calls, monkeypatch, tmp_path):
    monkeypatch.setattr(run, "ROOT", tmp_path)
    run.main(["docker"])
    assert calls[-1][1:] == ["compose", "up", "--build"]
    run.main(["docker", "down"])
    assert calls[-1][1:] == ["compose", "down"]
    assert (tmp_path / "audio").is_dir() and (tmp_path / "data/studio").is_dir()
    monkeypatch.setattr(run.shutil, "which", lambda c: None)
    assert run.main(["docker"]) == 1


def test_game_root_cmd(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("WC3UA_ROOT", str(tmp_path / "repo"))
    monkeypatch.delenv("WC3_GAME_ROOT", raising=False)
    monkeypatch.setattr(gameconf, "candidates", lambda: [])
    assert run.main(["game-root", str(tmp_path / "nope")]) == 1
    (tmp_path / "g/Data").mkdir(parents=True)
    assert run.main(["game-root", str(tmp_path / "g")]) == 0
    capsys.readouterr()
    assert run.main(["game-root"]) == 0
    out = capsys.readouterr().out
    assert "settings" in out and str(tmp_path / "g") in out


def test_setup_creates_venv_and_installs(tmp_path, monkeypatch, calls):
    monkeypatch.setattr(run, "ROOT", tmp_path)
    run.main(["setup", "--dev-only"])
    flat = [" ".join(c) for c in calls]
    assert any("uv venv" in c for c in flat) and any("requirements-dev.txt" in c for c in flat)
    assert not any("requirements.txt" in c.replace("requirements-dev.txt", "") for c in flat)


def test_setup_without_python311_or_uv(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(run, "ROOT", tmp_path)
    monkeypatch.setattr(run.shutil, "which", lambda c: None)
    monkeypatch.setattr(run, "_find_py311", lambda: None)
    assert run.main(["setup"]) == 1 and "uv" in capsys.readouterr().out


def test_core_test_lists_match_makefile():
    mk = (REPO / "Makefile").read_text(encoding="utf-8")
    for name, lst in (("CORE_TESTS_A", run.CORE_TESTS_A), ("CORE_TESTS_B", run.CORE_TESTS_B)):
        m = re.search(rf"^{name} := (.+)$", mk, re.M)
        assert m and m.group(1).split() == lst
    assert all((REPO / t).exists() for t in run.CORE_TESTS_A + run.CORE_TESTS_B + run.CORE_TESTS_C)


def test_cyrillic_output_survives_non_utf8_pipe():
    """CI windows-latest: stdout у конвеєр має cp1252 — `run.py` не має падати на кирилиці."""
    import os
    import subprocess
    import sys
    env = {**os.environ, "PYTHONIOENCODING": "cp1252"}
    env.pop("PYTHONUTF8", None)
    r = subprocess.run([sys.executable, "-I", "tools/run.py", "game-root", "--help"], capture_output=True, env=env,
                       cwd=Path(__file__).resolve().parent.parent)
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
    r = subprocess.run([sys.executable, "-I", "-c", "import sys; sys.path.insert(0, 'tools'); import run; run.utf8_stdio(); print('Готово')"],
                       capture_output=True, env=env, cwd=Path(__file__).resolve().parent.parent)
    assert r.returncode == 0 and "Готово" in r.stdout.decode("utf-8")
