# Ukrainian UI for Warcraft III Classic 1.31.1 (fdf + fonts)

Date: 2026-11-21. Follow-up to `fix-blank-ui.md`: after the Reforged-2.x fdf
overrides were moved out, the main menu rendered English again. This fix makes
the classic 1.31.1 interface fully Ukrainian without touching what already
works.

## What was built

Four 1.31-format fdf string lists with Ukrainian values, plus the
Cyrillic-capable font set the Russian language package ships:

| Installed into game root              | Size (ids) |
| ------------------------------------- | ---------- |
| `UI/framedef/globalstrings.fdf`       | 1089       |
| `UI/framedef/infopanelstrings.fdf`    | 111        |
| `UI/framedef/networkstrings.fdf`      | 205        |
| `UI/framedef/datestrings.fdf`         | 19         |
| `fonts/frizqt__.ttf`                  | —          |
| `fonts/dfheimd.ttf`, `fonts/dffn_b31.ttf` | —      |

`UI/framedef/` plain files are read directly by the client with
"Allow Local Files" enabled (proven by the earlier blank-menu experiment);
`fonts/` is a plain directory in this repack.

## How compatibility is guaranteed

The fdf **identifier set and byte structure are identical to the Russian
1.31 package** at
`/tmp/wc3-ru-root/Warcraft III Classic/Localizations/Russian/ruru.w3mod/ui/framedef/`
— the package proven to work with this exact client. `tools/fdf_strings.py`
rewrote only the quoted string VALUES line by line:

- id order identical (verified by re-extraction: 1089/1089, 111/111, 205/205,
  19/19);
- CRLF terminators, BOM (networkstrings.fdf has one) and trailing commas
  byte-identical to the Russian originals;
- all four Russian ids that the main menu needs are present:
  `KEY_CAMPAIGN` (Кампанія), `KEY_SINGLE_PLAYER` (Один гравець),
  `KEY_MULTIPLAYER` (Багатокористувацька), `KEY_LOAD_GAME` (Завантажити гру),
  `KEY_VIEW_REPLAY` (Переглянути повтор), `KEY_OPTIONS` (Налаштування),
  `KEY_CREDITS` (Титри), `KEY_BATTLE_NET` (Battle.net), `KEY_EXIT` (Вийти).

The earlier failure happened because Reforged-2.x fdfs have a different id
universe (2660 ids, no 1.31 menu ids). These fdfs are the opposite: the
1.31-era id set with Ukrainian text.

Note: the main menu ids carry the classic first-letter colour codes
(`|CffffffffК|Rампанія`), exactly like the Russian originals.

## Translation sources

Priority order as planned:

1. **warcraft-in-ua** (`/tmp/wc3-ua/WarCraft3-Reforged-Ukrainian-main/FULL
   [Interface and campaings]/_retail_/UI/framedef/*.fdf`): every id of the
   Russian 1.31 files exists there (100% overlap), so values were taken
   id-for-id. Format-specifier parity (`%s`, `%d`, colour codes) was checked
   per id.
2. **Manual retranslation** for 3 ids where the Reforged-era value uses a
   different placeholder set: `RESOURCE_UBERTIP_UPKEEP_INFO`,
   `ERROR_ID_CDKEY_INUSE`, `ERROR_ID_CDKEY_LANGUAGE`.

## Fonts

The Russian package's `frizqt__.ttf` is **Cyrillic Nimrod MT** (its internal
name table says so; byte-identical to files already present in this install
as `fonts/nim_____.ttf` / `fonts/nimrodmt.ttf`). No font merging was needed.

- `fonts/frizqt__.ttf` ← Russian package (overwrites the Latin Friz Quadrata;
  original backed up). Glyph check: **full coverage** of every character used
  in all four Ukrainian fdfs, including і Ї є Ґ.
- `fonts/dfheimd.ttf` ← Russian package; it is byte-identical to the existing
  `fonts/dfkgothicmd.ttf` (DFKGothic-Md). It lacks Upper І Ї and lower є і ї —
  the same 5-codepoint gap it has for any Ukrainian text; Russian (its design
  target) passes fully.
- `fonts/dffn_b31.ttf` ← Russian package (new file; nothing overwritten).
  Its cmap is Cyrillic-subset and it is not on the text path of these strings
  (Russian text fails the same check on it while the Russian package is proven
  working).

Checker: `tools/check_glyphs.py` (fonttools; parses cmap directly because the
game fonts carry subtables fontTools refuses to decompile).

## Why no other files were installed

The Russian package also carries `ui/*.txt`. Analysis:

- `helpstrings/tipstrings/triggerstrings/worldeditgamestrings/chathelp/
  newaccount/campaigninfo*` — Ukrainian versions from warcraft-in-ua are
  **already installed** in game root `UI/`.
- `miscui.txt`, `war3skins.txt` — configuration/skin files (paths, font
  sizes, textures), essentially no user-visible text.
- `campaignstrings(_exp).txt` — classic-era literal mission lists; 1.31.1
  instead reads `UI/campaigninfoclassic.txt` (already installed), whose
  `CAMP_*` ids resolve inside the client, not from local files.
- `worldedit*.txt`, `termsofservice-ruru.txt`, `mac*.txt`,
  `customkeyinfo.txt` etc. — World Editor / Battle.net TOS / macOS helpers,
  out of scope for the in-game interface.

## Install / verify / revert

Installed 2026-11-21 with backups and hashes in
`/Applications/Warcraft III Classic/Backups/fix2-ukrainian-ui/CHANGE-LOG.txt`.
Nothing was deleted; the only overwritten file is `fonts/frizqt__.ttf`.

Launcher check after install:

    .../WC3Patcher/backend/run-python.sh \
      .../WC3Patcher/backend/wc3-ui-assets.py \
      --game-root "/Applications/Warcraft III Classic" status
    → UI=enabled, UI_MISMATCHES=0

Revert:

    cp -p "/Applications/Warcraft III Classic/Backups/fix2-ukrainian-ui/fonts/frizqt__.ttf" \
          "/Applications/Warcraft III Classic/fonts/frizqt__.ttf"
    rm "/Applications/Warcraft III Classic/fonts/dfheimd.ttf" \
       "/Applications/Warcraft III Classic/fonts/dffn_b31.ttf"
    rm "/Applications/Warcraft III Classic"/UI/framedef/*.fdf   # dir was empty before

## What the user will see

Files are read at game start: **restart the game** (quit and press Play in
the launcher). The main menu shows: Кампанія, Один гравець, Багатокористувацька,
Завантажити гру, Переглянути повтор, Налаштування, Титри, Battle.net, Вийти —
in the classic font, now with full Cyrillic. Menus, options screens, info
panel (Броня/Атака tooltips), network/Battle.net messages and date strings
are Ukrainian. In-game unit/ability/item names remain Ukrainian from the
already-working `Units/*.txt`.
