@AGENTS.md

## Лише для Claude Code
- Скіли: `.claude/skills/` (`verify`, `add-catalog`, `add-processing-step`, `release-voice-pack`, `studio-e2e-test`,
  `game-change`) — тонкі покажчики на `docs/runbooks/`; зміст живе в docs, щоб його бачили й інші агенти.
- Субагенти — лише слабші й для повністю специфікованих задач; рев'ю — інлайн.
- Параметри Claude Code (`.claude/settings.json`) не чіпати й не пропонувати змін — автоматизація через git-хуки, CI, make.
