# AGENTS.md — wc3-ua-voice

Fan-made, non-commercial Ukrainian localization of Warcraft III Classic 1.31 (macOS): text UI plus a voice-over
studio (`tools/studio/`, stdlib + vanilla JS) where people record lines with their OWN voice. Quality target: «дубляж, що захоплює дух».
Talk to the owner in Ukrainian; code, commits and these instructions stay English-friendly. First read `docs/STATUS.md`.

## Setup and verify (Python is always `.venv/bin/python -I`)
- `make doctor` — what is missing (python 3.11/uv, ffmpeg, node, Chrome). `make setup-dev` — venv + dev deps (enough for verify).
- `make setup-refs` — PyCASC for `make refs` (game originals). `make setup` — both, plus `make hooks` (git pre-commit: guard + ruff).
- `make verify` — lint + guard + check-voices + core tests, ≤ 20 s, no Chrome: run before EVERY commit.
- `make check` — exactly what CI runs (verify + e2e in Chrome + coverage ratchet). `make studio` — studio on :8765.
- Tests never need the game: synthetic fixtures in `tests/conftest.py`.

## Task map (read only what the task needs, do not scan the repo)
| Task | Where |
|---|---|
| Studio architecture, data, extension points, pitfalls | `tools/studio/README.md` |
| New processing step (ffmpeg chain) | `docs/runbooks/add-processing-step.md` |
| New line source / catalog (campaign, races) | `docs/runbooks/add-catalog.md` |
| Studio UI test (Chrome, fake mic) | `docs/runbooks/studio-e2e-test.md` |
| Publish / review a community voice pack | `docs/runbooks/release-voice-pack.md`, `docs/CONTRIBUTING.md` |
| ANY write into the game folder | `.claude/skills/game-change/SKILL.md` |
| Terms UA ↔ code (дубль=take, репліка=line…) | `docs/GLOSSARY.md` |
| Expensive-to-rediscover facts (CASC, symlinks, Whisper, macOS) | `docs/gotchas.md` |
| Character, texts, voice bible | `docs/voice-bible/README.md` |
| Why things are the way they are | `docs/decisions/` (ADRs) |
| Menus / maps / local install | `docs/ukrainian-ui-131.md`, `docs/ukrainian-maps.md`, `docs/install-local.md` |
| Planned refactor of the studio | `docs/plans/modularize-studio.md` |
| Game path (`tools/gameconf.py`), cross-platform CLI (`tools/run.py`), Docker, UI hook | `docs/plans/game-path-ui.md`, `docs/install-local.md` |

## Hard boundaries
- Game folder (resolved by `tools/gameconf.py`: `WC3_GAME_ROOT` > `data/local/settings.json` > autodetect): only via `make install-voices` (dry run by default; `APPLY=1` only with the
  owner's explicit permission this session) and the `game-change` procedure. Never touch `Data/` or `Mods/`; delete nothing.
- Never commit game or proprietary audio, `reference*/`, `audio/`, `models/`, `game-files/`, `backups/`, `data/studio/`, `.env*`,
  `.venv`. No `git add -f`, no blind `git add -A`. Only FLAC voice packs in `voices/<author>/` are allowed (`make guard` enforces it).
- Original Blizzard line texts (RU/EN transcripts) never go into git: they live in gitignored `data/local/` (ADR 0005); tracked `data/transcripts-*.json` hold durations only (`make guard`).
- Commit author = the repo-local git config (personal email). Never write an email address or real name into files, commits or PRs.
  No attribution lines (no «Co-Authored-By», no «Generated with»). Push only with `git push origin`; never force-push main.
- Never edit `.claude/settings.json` and never propose changes to it (owner's rule). Automation goes through git hooks, CI, make targets.
- Clone only your own voice. No actor voices, no local TTS «for a try» (see `docs/decisions/0003-*`).
- No new dependencies without need: studio = stdlib + ffmpeg, UI = vanilla JS, no build step.

## Workflow
- Cross-platform (macOS/Windows/Linux/Docker): never hardcode a game path (use `gameconf`), no `/tmp`, `open`, `os.symlink` or `.venv/bin` assumptions
  outside `tools/run.py`/`opener.py`; open text files with `encoding="utf-8"`; every `make` target has a `python tools/run.py` equivalent.
- New behaviour → test next to it (`tests/`). `fail_under` in `pyproject.toml` only goes up (CI ratchet; currently 94).
- End of a session that changes state: update `docs/STATUS.md` (≤ 40 lines; decisions section is not revisited without the owner).
- Doc drift is tested (`tests/test_docs_sync.py`): new API route → server docstring + `tools/studio/README.md`; new make target → keep it real.
- Cheap and fast: read by the map, review inline, use sub-agents only for fully specified weaker tasks.

## Parallel work
- One git worktree + branch per feature (`git worktree add ../wc3-wt-<name> -b feat/<name>`); never edit another worktree's files.
- Keep a per-branch note in `docs/status/<branch>.md` (what is done / next / risks); it is folded into `docs/STATUS.md` at merge time.
- Hot files (`app.js`, `app.css`, `core.py`, `server.py`): small, focused diffs; rebase on main before merging.
- PR checklist: `.github/pull_request_template.md`. Agent-authored PRs: `docs/CONTRIBUTING.md` → «Для AI-агентів».
