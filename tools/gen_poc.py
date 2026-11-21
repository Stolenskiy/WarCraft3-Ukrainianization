#!/usr/bin/env python3
"""Generate Ukrainian voice variants for comparison (PoC).

Usage:
    .venv/bin/python -I tools/gen_poc.py <unit_ref_dir> <out_dir>

Reads texts from tools/poc_texts.json: {wav_name: {"text": ..., "xtts": ...}}
xtts = transliterated version for XTTS (і→и, ї→й, є→е, ґ→г).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
XTTS_LANG = "ru"  # base XTTS has no uk; transliterated Cyrillic read via ru tag


def translit_uk_to_ru(text: str) -> str:
    out = []
    for i, ch in enumerate(text):
        prev = text[i - 1] if i > 0 else ""
        if ch == "і":
            out.append("и")
        elif ch == "І":
            out.append("И")
        elif ch == "ї":
            out.append("й" if prev.lower() in "аеєиіоуюя" else "йи")
        elif ch == "Ї":
            out.append("Й")
        elif ch == "є":
            out.append("йе" if not prev or prev.lower() not in "бвгджзйклмнпрстфхцчшщ" else "е")
        elif ch == "Є":
            out.append("Є")
        elif ch == "ґ":
            out.append("г")
        elif ch == "Ґ":
            out.append("Г")
        else:
            out.append(ch)
    return "".join(out)


def main() -> None:
    unit_dir = Path(sys.argv[1])
    out_dir = Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    texts = json.loads((ROOT / "tools" / "poc_texts.json").read_text())

    # --- Piper (native Ukrainian voice, no cloning) ---
    from piper import PiperVoice, SynthesisConfig

    voice = PiperVoice.load(
        str(ROOT / "models/piper/uk_UA-ukrainian_tts-medium.onnx")
    )
    cfg = SynthesisConfig(length_scale=1.0)
    for name, spec in texts.items():
        wav_out = out_dir / f"{Path(name).stem}_piper.wav"
        with wave_open(str(wav_out)) as w:
            voice.synthesize_wav(spec["text"], w, syn_config=cfg)
        print("piper:", wav_out.name)

    # --- XTTS (cloned timbre from Russian reference) ---
    from TTS.api import TTS

    snap = Path.home() / (
        ".cache/huggingface/hub/models--tts-hub--XTTS-v2/"
        "snapshots/345b56f6fbe25cca7103f7f34e471b8fe8e4945f"
    )
    tts = TTS(model_path=str(snap), config_path=str(snap / "config.json"))
    tts.to("cpu")
    for name, spec in texts.items():
        ref = unit_dir / name
        if not ref.exists():
            print("no ref for", name)
            continue
        wav_out = out_dir / f"{Path(name).stem}_xtts.wav"
        tts.tts_to_file(
            text=spec.get("xtts") or translit_uk_to_ru(spec["text"]),
            speaker_wav=str(ref),
            language=XTTS_LANG,
            file_path=str(wav_out),
        )
        print("xtts:", wav_out.name)


def wave_open(path):
    import wave

    return wave.open(path, "wb")


if __name__ == "__main__":
    main()
