# Для власника репозиторію: налаштування, які робляться вручну

Агенти не змінюють налаштування GitHub (і `.claude/settings.json`). Один раз виконайте самі.

## Локально
1. `make setup-dev` (або `make setup`), потім `make hooks` — вмикає `.githooks/pre-commit` (guard + ruff). Перевірка: `make doctor`.

## Branch protection для `main` (GitHub → Settings → Branches → Add rule)
1. **Require a pull request before merging**; увімкнути **Require review from Code Owners** (`.github/CODEOWNERS` → `@Stolenskiy`).
2. **Require status checks to pass**: обрати перевірку `check` із workflow CI (з'являється після першого запуску); **Require branches to be up to date**.
3. **Do not allow force pushes**; **Do not allow deletions**; за бажання — **Require linear history** і **Include administrators**.
4. Settings → Actions → General → Workflow permissions: **Read repository contents**; fork-PR — **Require approval for first-time contributors**.
5. Settings → Code security: увімкнути Dependabot alerts/security updates (версії вже в `.github/dependabot.yml`) і secret scanning.
6. Мітки для issue-форм (`bug`, `studio`, `text`, `voices`) — створіть у Issues → Labels.

## Процес злиття
- `make check` зелений локально → PR → CI → ревʼю (для `voices/`, `.github/`, `tools/install_voices.py`, `AGENTS.md` — власник).
- Під час злиття гілки згорніть `docs/status/<гілка>.md` у `docs/STATUS.md` і видаліть нотатку.
- Кожен `fail_under` лише вгору (CI-храповик).
