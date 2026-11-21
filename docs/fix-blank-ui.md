# Fix report: blank UI buttons in "Warcraft III Classic" (1.31.1 repack)

Date: 2026-11-21. Game: `/Applications/Warcraft III Classic` (lmmortal-Repack),
client 1.31.1.2i73 Public Test x86_64, launched via `x86_64/Warcraft III.app`.

## Symptom

Main menu renders blue buttons with **no text at all** (not English, not
Ukrainian). Only the "Battle.net" label renders.

## Root cause (verified against the files)

The warcraft-in-ua Reforged-2.x translation was copied into the game root,
including `UI/framedef/*.fdf`. With "Allow Local Files" enabled the 1.31.1
client reads game-root `UI/framedef/*.fdf` and these files **replace** its
built-in string lists.

The Reforged 2.x `globalstrings.fdf` uses a different identifier set: the
1.31.1 main menu requests identifiers such as `SINGLE_PLAYER`, `CAMPAIGN`,
`CREDITS`, `EXIT`, `BATTLE_NET`, and the copied file contains none of them
(2660 identifiers present; zero matches for the 1.31 menu ids). Missing
identifier = empty text = blank button. Strings that exist in both eras
(e.g. "Battle.net") still render, which matches the symptom exactly.

Secondary finding: the copied `fonts/frizqt__.ttf` (the classic main font)
contains **no Cyrillic glyphs**, so a Ukrainian *Classic-mode* menu would not
render even with correct identifiers. A Ukrainian classic menu needs both
1.31-format translated fdfs and a Cyrillic Friz Quadrata.

Note on the launcher: its backend (`WC3Patcher/`) has no "switch to Reforged
2.0.4" operation — the client binary is 1.31.1 and stays 1.31.1. Its "Reforged
UI" package only symlinks textures (`UI/glues|widgets|feedback|console|cursor`,
all `.blp`; verified against `Tools/State/Reforged UI/state.json`, 1065 files,
`UI_MISMATCHES=0` after the fix) and cannot affect text. So mode switching was
not a viable path; the fdf overrides themselves were the only problem.

## What was changed

Moved (never deleted) into `/Applications/Warcraft III Classic/Backups/fix-20261121/UI/framedef/`:

- `UI/framedef/datestrings.fdf`
- `UI/framedef/globalstrings.fdf`
- `UI/framedef/infopanelstrings.fdf`
- `UI/framedef/networkstrings.fdf`

Everything else was left in place deliberately: `fonts/` (Latin intact),
`Units/*.txt` (plain string tables — Ukrainian unit/ability names in-game,
natively parsed by 1.31.1), `UI/*.txt` (not used by the main menu),
launcher-managed symlinks and `Tools/` state. Full details and SHA-256 hashes:
`Backups/fix-20261121/CHANGE-LOG.txt`.

## Result / what the user should see

Press Play in the launcher. The main menu buttons show English text again
(Campaign / Single Player / Options / Credits / Exit). Ukrainian unit and
ability names still appear in-game (from `Units/*.txt`).

Caveat: the Reforged balance patch is installed (`balance-status` = installed),
but the Ukrainian `Units/*Strings.txt` files overwrite 17 of the 36 payload
string files, so the launcher's patch status shows "not installed". If the
launcher's install/repair for the balance patch is run, it will overwrite the
Ukrainian unit strings with English payload copies.

## Revert

    cp -p "/Applications/Warcraft III Classic/Backups/fix-20261121/UI/framedef/"*.fdf \
          "/Applications/Warcraft III Classic/UI/framedef/"

(brings back the pre-fix state, including the blank buttons).

## Path to a Ukrainian interface (follow-up work)

The 1.31.1 client needs its own identifier set. Concretely:

1. Build 1.31-format `UI/framedef` fdfs: take the 1.31.1 `globalstrings.fdf`
   identifier list and fill in Ukrainian values (merge, don't replace, the
   2.x translation).
2. Ship a Cyrillic-capable `fonts/frizqt__.ttf` (and check `bl.ttf` etc.).
3. Keep the current `Units/*.txt` approach — it already works.
