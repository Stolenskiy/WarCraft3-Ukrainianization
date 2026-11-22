# feat/ai-studio-backend

Готово: `tools/aistudio/` (params, refs, jobs, engines/, setup, api, cli), `run.py ai-generate|ai-setup|ai-status|ai-consent`, ліцензія ШІ-реплік
CC BY-NC 4.0 (ADR 0007, voices.py, check_voices), guard проти ключів API. Проводка UI — `docs/plans/ai-studio-ui.md`; новий двигун — `docs/runbooks/add-ai-engine.md`.
Смоук (Fish, MPS, 1 коротка репліка, n=1): ≈ 4 хв разом із завантаженням моделі та метриками; CER 0.167, схожість 0.80.
Далі: маршрути/UI (фаза 2), справжній ElevenLabs-двигун (за ключем), ліцензійний рядок у модалці встановлення, ревізія пілотних тегів стилю.
Ризики: Windows/CUDA шлях `ai-setup` не перевірено на реальній машині; Whisper-CER залежить від mlx_whisper (інакше `null`).
