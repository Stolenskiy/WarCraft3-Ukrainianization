"""Робітник ШІ-очищення запису Sidon (ONNX): прибирає луну й шум, відновлює частоти. Запускається в .venv-enhance.

  python -I sidon_worker.py spec.json
spec: {"model": тека з int8/sidon-*.onnx і frontend/preprocessor_config.json, "jobs": [{"in": wav, "out": wav}]}
stdout (JSONL): {"loaded": с} один раз, далі на кожне завдання {"out": шлях, "sec": с} або {"out": шлях, "error": текст}.
Вихід — 48 кГц float WAV тієї ж тривалості; гучність і формат гри робить студія (tools/aistudio/enhance.py).
Модель: Sidon v0.1 (sarulab-speech, MIT) у ONNX-експорті soniqo/Sidon-ONNX (MIT); вхід 16 кГц, вихід 48 кГц.
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort
import soundfile as sf
import soxr
from transformers import SeamlessM4TFeatureExtractor

SR_IN, SR_OUT = 16000, 48000
PAD = 0.1                     # с тиші з кожного боку: модель не «з’їдає» перший і останній склад
PEAK = 0.9                    # вхід нормується за піком, як в офіційному infer.py Sidon


def restore(x: np.ndarray, sr: int, fe, pred, voc) -> np.ndarray:
    if x.ndim > 1:
        x = x.mean(axis=1)
    x16 = soxr.resample(x.astype(np.float32), sr, SR_IN)
    x16 = x16 / max(1e-6, float(np.abs(x16).max())) * PEAK
    pad = int(PAD * SR_IN)
    x16 = np.pad(x16, (pad, pad))
    feats = fe(x16, sampling_rate=SR_IN, return_tensors="np")["input_features"].astype(np.float32)
    h = pred.run(None, {"input_features": feats})[0]
    y = voc.run(None, {"features": h})[0].reshape(-1)
    cut = pad * SR_OUT // SR_IN
    return y[cut:len(y) - cut] if len(y) > 2 * cut else y


def main() -> int:
    spec = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    m = Path(spec["model"])
    t0 = time.time()
    so = ort.SessionOptions()
    so.log_severity_level = 3                                 # без попереджень constant_folding у stderr
    pred = ort.InferenceSession(str(m / "int8/sidon-predictor.onnx"), so, providers=["CPUExecutionProvider"])
    voc = ort.InferenceSession(str(m / "int8/sidon-vocoder.onnx"), so, providers=["CPUExecutionProvider"])
    fe = SeamlessM4TFeatureExtractor.from_pretrained(str(m / "frontend"))
    print(json.dumps({"loaded": round(time.time() - t0, 2)}), flush=True)
    for job in spec["jobs"]:
        t1 = time.time()
        try:
            x, sr = sf.read(job["in"], dtype="float32")
            y = restore(x, sr, fe, pred, voc)
            if not np.isfinite(y).all() or not len(y):
                raise ValueError("порожній або зіпсований вихід моделі")
            sf.write(job["out"], y, SR_OUT, subtype="FLOAT")
            print(json.dumps({"out": job["out"], "sec": round(time.time() - t1, 2)}), flush=True)
        except Exception as ex:  # noqa: BLE001 — один збійний файл не зупиняє партію
            print(json.dumps({"out": job["out"], "error": f"{type(ex).__name__}: {ex}"}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
