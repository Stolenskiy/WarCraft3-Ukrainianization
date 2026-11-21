#!/usr/bin/env python3
"""Автотест студії запису (без участі людини) у тимчасовій копії репозиторію.

    .venv/bin/python -I tools/test_record_studio.py          # з реальним мікрофоном (1 с запису)
    .venv/bin/python -I tools/test_record_studio.py --no-mic # без мікрофона (синтетичний take)

Перевіряє: міграцію старого стану, запис, унікальну нумерацію після видалення,
затвердження → файл для гри, перезатвердження, видалення затвердженої спроби,
відновлення, редагування тексту, перемикання юнітів, збереження між запусками.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
NO_MIC = "--no-mic" in sys.argv


def make_root() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="studio-test-"))
    (tmp / "reference/units").mkdir(parents=True)
    os.symlink(REPO / "reference/units/orc", tmp / "reference/units/orc")
    shutil.copytree(REPO / "docs/voice-bible", tmp / "docs/voice-bible")
    (tmp / "data").mkdir()
    for f in (REPO / "data").glob("transcripts-*.json"):
        shutil.copy(f, tmp / "data")
    shutil.copy(REPO / "data/watermark-quarantine.json", tmp / "data")
    # старий стан першої версії + 2 старі спроби + «загублений» файл
    takes = tmp / "audio/self-recorded/peon"
    takes.mkdir(parents=True)
    for n in (1, 2):
        synth(takes / f"peonyes1.take{n}.wav", 0.8)
    synth(takes / "peonyes1.wav.take1.wav", 1.0)
    (tmp / "data/record-session-peon.json").write_text(
        '{"Peonyes1.wav": {"approved": null, "takes": ["peonyes1.take1.wav", "peonyes1.take2.wav"]}}')
    return tmp


def synth(path: Path, sec: float) -> None:
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    f"sine=frequency=440:sample_rate=22050:duration={sec}",
                    "-ac", "1", "-sample_fmt", "s16", str(path)], check=True)


def main() -> None:
    root = make_root()
    os.environ["WC3UA_ROOT"] = str(root)
    sys.path.insert(0, str(REPO / "tools"))
    import record_studio as rs
    from tkinter import messagebox
    messagebox.askyesno = lambda *a, **k: True          # «Так» на всі підтвердження
    errors = []
    messagebox.showerror = lambda t, m, **k: errors.append(f"{t}: {m}")
    messagebox.showinfo = lambda *a, **k: None

    app = rs.Studio()
    app.withdraw()
    ok = lambda c, msg: print(("  ✔ " if c else "  ✘ ") + msg) or (c or failures.append(msg))
    failures: list[str] = []

    ok(app.unit == "peon", "стартовий юніт — Роботяга")
    ph = app.phrases[app.idx]
    e = app._entry(ph)
    files = [t["file"] for t in e["takes"]]
    ok(files[:2] == ["peonyes1.take1.wav", "peonyes1.take2.wav"], "міграція старого стану")
    ok("peonyes1.wav.take1.wav" in files, "знайдено загублений файл спроби")
    ok(ph.fname == "peonyes1.wav" and "Сделаю" in ph.ru, f"рос. текст показано: {ph.ru!r}")
    ok(app.var_ua.get() == "Зроблю.", "український текст підставлено")

    # запис
    if NO_MIC:
        t = app._next_take_file(ph); synth(t, 0.7)
        e["takes"].append({"file": t.name, "created": rs.now(), "deleted": None})
    else:
        app.var_autoplay.set(False)
        app._start_record()
        end = __import__("time").monotonic() + 1.8
        while __import__("time").monotonic() < end:
            app.update(); __import__("time").sleep(0.05)
        app._stop_record()
        ok(not errors, f"запис з мікрофона без помилок {errors}")
    act = app._active_takes(e)
    ok(act[-1]["file"] == "peonyes1.take3.wav", f"нова спроба = take3 ({act[-1]['file']})")

    app._approve(act[-1])
    ok(ph.game_path.exists() and e["approved"] == "peonyes1.take3.wav", "затвердження → файл для гри")
    ok(str(ph.game_path).endswith("game-files/Units/orc/peon/peonyes1.wav"), "шлях як у грі")
    app._approve(act[0])
    ok(e["approved"] == "peonyes1.take1.wav", "перезатвердження іншої спроби")
    app._delete(act[0])
    ok(e["approved"] is None and not ph.game_path.exists(), "видалення затвердженої знімає затвердження")
    ok((root / "audio/self-recorded/peon/_deleted/peonyes1.take1.wav").exists(), "файл у _deleted/")
    t4 = app._next_take_file(ph)
    ok(t4.name == "peonyes1.take4.wav", f"нумерація не перезаписує ({t4.name})")
    app._restore(e["takes"][0])
    ok((root / "audio/self-recorded/peon/peonyes1.take1.wav").exists(), "відновлення спроби")

    app.var_ua.set("Зроблю, хазяїне.")
    app._save_text()
    ok(e["ua_text"] == "Зроблю, хазяїне.", "редагування тексту збережено")
    app.show_deleted = True
    app._render_takes()

    for u, _ in app.units:
        app._load_unit(u)
        ok(len(app.phrases) > 0, f"юніт {u}: {len(app.phrases)} реплік, "
                                 f"підказок UA {sum(1 for p in app.phrases if p.ua_hint)}")
    app._on_close()

    # перезапуск — усе на місці
    app2 = rs.Studio(); app2.withdraw()
    e2 = app2.store.entry("peon", "peonyes1.wav")
    ok(e2["ua_text"] == "Зроблю, хазяїне." and len(e2["takes"]) == 4 and len(e2["history"]) >= 5,
       f"стан відновлено після перезапуску (текст={e2['ua_text']!r}, спроб={len(e2['takes'])}, журнал={len(e2['history'])})")
    app2.destroy()
    shutil.rmtree(root)
    print("\nOK — усі перевірки пройдено" if not failures else f"\nПРОВАЛ: {failures}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
