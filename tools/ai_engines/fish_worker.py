"""Робітник Fish Speech S2-Pro: окремий процес у `.venv-fish` основного репозиторію (tools/ai_voice.py).

Вхід — JSON-файл завдань: {"repo": <tools/fish-speech>, "model": <models/fish-s2-pro>, "jobs": [
  {"out": raw.wav, "text": str, "seed": int, "temperature": float, "top_p": float,
   "refs": [{"audio": wav, "text": str}]}]}
Модель вантажиться один раз, пишемо сирі wav (44.1 кГц), друкуємо по рядку JSON на завдання. Після виходу пам'ять звільнена.
"""
import json
import sys
import time
from pathlib import Path


def main() -> None:
    spec = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    sys.path.insert(0, spec["repo"])
    import numpy as np
    import soundfile as sf
    import torch
    from fish_speech.inference_engine import TTSInferenceEngine
    from fish_speech.models.dac.inference import load_model as load_decoder
    from fish_speech.models.text2semantic.inference import launch_thread_safe_queue
    from fish_speech.utils.schema import ServeReferenceAudio, ServeTTSRequest

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    precision = torch.bfloat16
    t0 = time.time()
    queue = launch_thread_safe_queue(checkpoint_path=spec["model"], device=device, precision=precision,
                                     compile=False, reference_sampling=None)
    decoder = load_decoder(config_name="modded_dac_vq", checkpoint_path=str(Path(spec["model"]) / "codec.pth"),
                           device=device)
    engine = TTSInferenceEngine(llama_queue=queue, decoder_model=decoder, precision=precision, compile=False,
                                model_family="s2")
    print(json.dumps({"loaded": round(time.time() - t0, 1)}), flush=True)
    for job in spec["jobs"]:
        t1 = time.time()
        refs = [ServeReferenceAudio(audio=Path(r["audio"]).read_bytes(), text=r["text"]) for r in job["refs"]]
        req = ServeTTSRequest(text=job["text"], references=refs, format="wav", seed=job["seed"],
                              temperature=job["temperature"], top_p=job["top_p"], max_new_tokens=int(job.get("max_new", 512)))
        audio, rate, err = None, 44100, None
        for res in engine.inference(req):
            if res.code == "final" and isinstance(res.audio, tuple):
                rate, audio = res.audio
            elif res.code == "error":
                err = str(res.error)
        if audio is None:
            print(json.dumps({"out": job["out"], "error": err or "no audio"}), flush=True)
            continue
        sf.write(job["out"], np.asarray(audio, dtype=np.float32), int(rate))
        print(json.dumps({"out": job["out"], "sec": round(time.time() - t1, 1), "rate": int(rate)}), flush=True)


if __name__ == "__main__":
    main()
