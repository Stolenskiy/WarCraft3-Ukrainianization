"""guard_no_audio: блокує аудіо/секрети/теки гри (навіть через git add -f), пропускає пакети голосів."""
import subprocess
from pathlib import Path

import check_voices
import guard_no_audio as guard
import pytest
from test_voices import mkroot, pub


def git(root, *a):
    subprocess.run(["git", *a], cwd=root, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "g"
    r.mkdir()
    git(r, "init", "-q")
    return r


def put(root, rel, data=b"x"):
    p = Path(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return p


def test_blocks_staged_wav(repo):
    put(repo, "take.wav")
    git(repo, "add", "-f", "take.wav")
    assert set(guard.git_files(repo)) == {"take.wav"} and guard.main(repo) == 1


def test_blocks_force_added_reference(repo):
    put(repo, "reference/units/orc/peon/peonyes1.txt")
    git(repo, "add", "-f", "reference")
    assert guard.main(repo) == 1


def test_blocks_env_and_secrets(repo):
    for rel in (".env", "sub/.env.local", "k.pem", "data/studio/orc.json", "backups/a.txt", "m/a.m4a", "x.mpq"):
        assert guard.violations([rel]) == [rel], rel


def test_allows_voices_flac_and_json(repo):
    for rel in ("voices/alice/units/orc/peon/peonyes1.flac", "voices/alice/voice.json", "voices/alice/manifest.json",
                "voices/alice/LICENSE.md", "voices/LICENSE.md", "tools/studio/web/app.js", ".env.example"):
        put(repo, rel)
        git(repo, "add", "-f", rel)
    assert guard.main(repo) == 0


def test_blocks_non_flac_audio_inside_voices(repo):
    assert guard.violations(["voices/alice/units/orc/peon/x.wav", "voices/alice/notes.m4a"]) == [
        "voices/alice/notes.m4a", "voices/alice/units/orc/peon/x.wav"]


def test_repo_itself_is_clean():
    assert guard.main() == 0


def test_check_voices_and_guard_agree(tmp_path):
    root = mkroot(tmp_path)
    git(root, "init", "-q")
    pub(root)
    git(root, "add", "-f", "voices")
    assert check_voices.check(root) == [] and guard.main(root) == 0      # справжній пакет — обидва «за»
    put(root, "voices/LICENSE.md", b"CC BY 4.0")                        # спільна ліцензія в корені voices/
    put(root, "voices/alice/LICENSE.md", b"CC BY 4.0")                  # дозволений обома
    git(root, "add", "-f", "voices")
    assert check_voices.check(root) == [] and guard.main(root) == 0
    put(root, "voices/alice/units/orc/peon/extra.wav")                  # сторонній файл у пакеті
    git(root, "add", "-f", "voices")
    assert check_voices.check(root) != [] and guard.main(root) == 1     # обидва «проти»


def test_blocks_local_dir_and_original_texts_in_tracked_transcripts(repo):
    assert guard.violations(["data/local/transcripts-orc-peon.json"]) == ["data/local/transcripts-orc-peon.json"]
    put(repo, "data/transcripts-orc-peon.json", b'{"a.wav": {"duration": 1.0}}')
    git(repo, "add", "-f", "data")
    assert guard.main(repo) == 0                                   # лише тривалості — можна
    put(repo, "data/transcripts-orc-peon.json", '{"a.wav": {"text": "Сделаю.", "duration": 1.0}}'.encode())
    git(repo, "add", "-f", "data")
    assert guard.main(repo) == 1                                   # поле text — заборонено
