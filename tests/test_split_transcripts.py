"""split_transcripts: тексти -> data/local/, у git лише тривалості; ідемпотентно й без втрат."""
import json

import split_transcripts as st


def wr(p, d):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, ensure_ascii=False))


def test_split_is_idempotent_and_lossless(tmp_path):
    full = {"a.wav": {"text": "Сделаю.", "duration": 0.8}, "b.wav": {"text": "Да.", "duration": 1.0}}
    wr(tmp_path / "data/transcripts-orc-peon.json", full)
    assert st.split(tmp_path)["texts"] == 2
    tracked = json.loads((tmp_path / "data/transcripts-orc-peon.json").read_text())
    assert tracked == {"a.wav": {"duration": 0.8}, "b.wav": {"duration": 1.0}}
    local = tmp_path / "data/local/transcripts-orc-peon.json"
    assert json.loads(local.read_text()) == full
    assert st.split(tmp_path)["files"] == 0 and json.loads(local.read_text()) == full   # повторний запуск нічого не губить


def test_existing_local_wins_and_merges(tmp_path):
    wr(tmp_path / "data/local/transcripts-x.json", {"a.wav": {"text": "МОЄ", "duration": 1.0}})
    wr(tmp_path / "data/transcripts-x.json", {"a.wav": {"text": "інше", "duration": 2.0}, "b.wav": {"text": "Б", "duration": 1.0}})
    st.split(tmp_path, strip=False)
    assert json.loads((tmp_path / "data/transcripts-x.json").read_text())["a.wav"]["text"] == "інше"   # --local-only не чіпає git-файл
    loc = json.loads((tmp_path / "data/local/transcripts-x.json").read_text())
    assert loc["a.wav"]["text"] == "МОЄ" and loc["b.wav"]["text"] == "Б"
