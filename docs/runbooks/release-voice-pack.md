# Runbook: випуск / перевірка пакета голосу

Пакет: `voices/<нік>/{voice.json, manifest.json, [LICENSE.md], units/<раса>/<юніт>/<файл>.flac}` (CC BY 4.0, `voices/LICENSE.md`).

## Автор
1. Затвердити дублі в студії → «Голоси спільноти» → «Опублікувати» або `make publish-voice AUTHOR=<нік> CONSENT=1`
   (лише ВЛАСНИЙ голос; публікатор не запускає git і не бере оригінали гри).
2. `make verify` (guard + `check-voices` + тести); команди git підказує публікатор: гілка `voices/<нік>`, `git add voices/<нік>`, PR.
3. ШІ-репліки позначені `"ai": true`; пошти/контактів немає (лише нікнейм).

## Ревʼю чужого PR
- Змінено лише `voices/<нік>/` автора PR; `make check-voices` і `make guard` зелені (CI те саме).
- `voice.json`: `license` = CC BY 4.0, `consent: true`, `id` = назва теки. FLAC 22050 Hz mono 16 біт, ≤ 1 МБ, є в `manifest.json` (sha256).
- Репліка є в `data/inventory-units.csv`; FLAC не збігається з оригіналом (`check_voices` відхиляє, якщо `.originals.json` є локально).
- На слух вибірково: голос один і той самий автор; без чужих голосів і оригіналів Blizzard.
- Розмір ≈ 60 МБ на автора у звичайному git (ADR 0002); багато пакетів → Git LFS/Releases — рішення власника.
