#!/usr/bin/env python3
"""Студія запису української озвучки юніта — інтерактивна сесія в терміналі.

Запуск (у Terminal.app, не через Claude):
    cd ~/Desktop/Projects/wc3-ua-voice
    .venv/bin/python -I tools/record_session.py peon

Керування на кожній фразі:
    п  — прослухати російський референс
    з  — записати спробу (Enter → говорите → Enter — зупинити)
    пп — прослухати всі спроби
    о N — затвердити спробу N (напр. «о 2»)
    д  — перейти до наступної фрази (потрібне затвердження або --skip)
    в  — вийти; прогрес зберігається
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UNIT = sys.argv[1] if len(sys.argv) > 1 else "peon"
REF_DIR = ROOT / f"reference/units/orc/{UNIT}"
TEXTS_FILE = ROOT / "tools/poc_texts.json" if UNIT == "peon" else None
STATE_FILE = ROOT / f"data/record-session-{UNIT}.json"
TAKES_DIR = ROOT / f"audio/self-recorded/{UNIT}"
GAME_DIR = ROOT / f"game-files/Units/Orc/Peon"
MIC = ":0"  # MacBook Pro Microphone
SR = 22050

# оригінальна назва файлу в грі (CamelCase) -> ключ референсу
GAME_NAMES = {k: k.replace("peon", "Peon") for k in json.loads(TEXTS_FILE.read_text())}


def play(path: Path) -> None:
    subprocess.run(["afplay", str(path)], check=False)


def record(out: Path) -> None:
    """Запис до другого Enter (ffmpeg у фоні)."""
    input("    ▶ ГОТОВИЙ? Enter — почати запис... ")
    print("    🔴 ЗАПИС... (Enter — зупинити)")
    proc = subprocess.Popen(
        ["ffmpeg", "-y", "-f", "avfoundation", "-i", MIC, "-ar", str(SR),
         "-ac", "1", "-sample_fmt", "s16", str(out)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    input()
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
    if out.exists() and out.stat().st_size > 1000:
        print(f"    ✔ збережено: {out.name}")
    else:
        print("    ✗ запис не вдався (перевірте дозвіл мікрофона для Terminal)")
        out.unlink(missing_ok=True)


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {k: {"approved": None, "takes": []} for k in GAME_NAMES}


def save_state(st):
    STATE_FILE.write_text(json.dumps(st, ensure_ascii=False, indent=2))


def duration(path: Path) -> str:
    r = subprocess.run(["afinfo", str(path)], capture_output=True, text=True)
    for line in r.stdout.splitlines():
        if "estimated duration" in line:
            return f"{float(line.split(':')[1].strip().split()[0]):.2f}s"
    return "?"


def main() -> None:
    texts = json.loads(TEXTS_FILE.read_text())
    state = load_state()
    TAKES_DIR.mkdir(parents=True, exist_ok=True)
    GAME_DIR.mkdir(parents=True, exist_ok=True)

    total = len(GAME_NAMES)
    done = sum(1 for v in state.values() if v["approved"] is not None)
    print(f"\n🎬 СТУДІЯ ОЗВУЧЕННЯ: {UNIT} | затверджено {done}/{total}")
    print("   команди: п=референс, з=запис, пп=спроби, о N=затвердити, д=далі, в=вихід\n")

    for key, game_name in GAME_NAMES.items():
        if state[key]["approved"] is not None:
            continue
        ref = REF_DIR / key
        phrase = texts[key]["text"]
        while True:
            print(f"━━━ {game_name} ━━━")
            print(f"   УКР: «{phrase}»")
            print(f"   тривалість оригіналу: {duration(ref)}")
            cmd = input("   команда> ").strip().lower()
            if cmd == "п":
                play(ref)
            elif cmd == "з":
                n = len(state[key]["takes"]) + 1
                take = TAKES_DIR / f"{key}.take{n}.wav"
                record(take)
                if take.exists():
                    state[key]["takes"].append(take.name)
                    save_state(state)
                    print("    ▶ прослуховування...", end=" ")
                    play(take)
            elif cmd == "пп":
                for t in state[key]["takes"]:
                    print(f"    ▶ {t}", end=" ")
                    play(TAKES_DIR / t)
            elif cmd.startswith("о"):
                parts = cmd.split()
                if len(parts) == 2 and parts[1].isdigit():
                    n = int(parts[1])
                    if 1 <= n <= len(state[key]["takes"]):
                        take = TAKES_DIR / state[key]["takes"][n - 1]
                        dst = GAME_DIR / game_name
                        shutil.copy2(take, dst)
                        state[key]["approved"] = state[key]["takes"][n - 1]
                        save_state(state)
                        done += 1
                        print(f"    ✅ ЗАТВЕРДЖЕНО take{n} → {dst} ({done}/{total})")
                        break
                print("    ? формат: о N")
            elif cmd == "д":
                print("    ⚠ без затвердження — фраза лишається незаписаною")
                break
            elif cmd == "в":
                print(f"    збережено. Прогрес: {done}/{total}")
                return
            else:
                print("    ? невідома команда")
    print(f"\n🎉 ВСІ ФРАЗИ ЗАТВЕРДЖЕНО ({done}/{total})!")
    print(f"   Файли: {GAME_DIR}")
    print("   Встановлення в гру: скопіюйте game-files/Units/Orc/Peon/ у корінь гри.")


if __name__ == "__main__":
    main()
