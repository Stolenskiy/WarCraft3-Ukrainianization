"""Схожість голосу: косинус між x-vector (microsoft/wavlm-base-plus-sv) — окремий процес у `.venv-fish`.

Вхід — JSON {"pairs": [{"id": str, "wav": кандидат, "refs": [wav власних дублів]}]};
вихід — по рядку JSON {"id", "similarity"} (середній косинус до власних дублів, 0..1).
"""
import json
import sys
from pathlib import Path


def main() -> None:
    import librosa
    import torch
    from transformers import AutoFeatureExtractor, WavLMForXVector

    spec = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    name = "microsoft/wavlm-base-plus-sv"
    fe, model = AutoFeatureExtractor.from_pretrained(name), WavLMForXVector.from_pretrained(name).eval()
    cache: dict[str, torch.Tensor] = {}

    def emb(path: str) -> torch.Tensor:
        if path not in cache:
            y, _ = librosa.load(path, sr=16000, mono=True)
            inp = fe(y, sampling_rate=16000, return_tensors="pt")
            with torch.no_grad():
                cache[path] = torch.nn.functional.normalize(model(**inp).embeddings, dim=-1)[0]
        return cache[path]

    for p in spec["pairs"]:
        sims = [float(emb(p["wav"]) @ emb(r)) for r in p["refs"]]
        print(json.dumps({"id": p["id"], "similarity": round(sum(sims) / len(sims), 4)}), flush=True)


if __name__ == "__main__":
    main()
