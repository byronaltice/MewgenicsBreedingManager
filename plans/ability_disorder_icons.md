# Ability & Disorder Icon Integration Plan

## Goal

Display each ability's and disorder's in-game icon in the Breed Priority UI (tooltips, chips), e.g. show the real "Blow Kiss" icon next to the ability name.

## What we know

- **Ability icons** are MovieClip symbols inside `defect-investigation/game-files/resources/gpak-video/swfs/ability_icons.swf` (and `ui.swf` for some). The icon symbol name comes from `graphics.animation` in each ability's GON entry under `defect-investigation/game-files/resources/gpak-text/data/abilities/*.gon`.
- **`meta.ability_icon`** overrides redirect to another ability's icon symbol (~14 cases, e.g. `FetusSpit` → `Spit`).
- **`meta.type_icon`** + **`meta.icon_shell_frame`** are category badge + frame overlays (composited on top of the base icon).
- **Disorders/mutations have no icon field in any GON.** Visual identity comes from `catparts.swf` symbols keyed by `(slot, mutation_id)` — the exact symbol-naming scheme inside `catparts.swf` still needs confirmation.
- **`resources.gpak`** is an "NH" magic-header indexed archive (~4.9 GB, uncompressed wrapper). Not used at runtime — all assets are already pre-extracted alongside it. The app will not parse the gpak.
- An existing SWF parser lives at `defect-investigation/scripts/extract-symbols/swf_parser.py` (reads `.swf` files directly, extracts bitmap symbols to PNG). Existing wrappers: `extract_all.py`, `extract_final_icons.py`, `stage_icons_to_assets.py`.

## Strategy: ship pre-rendered PNGs in the repo

- Run the SWF extractor once (offline), commit the resulting PNGs under `assets/icons/`.
- App loads PNGs from `assets/` at runtime via a small `IconProvider` with `QPixmapCache`.
- No gpak parsing, no SWF parsing at runtime, no dependency on the game being installed.
- Expected repo footprint: a few MB for a few hundred ~48px icons.

## Plan

### Phase 1 — Extract ability icons to `assets/`
1. Reuse `defect-investigation/scripts/extract-symbols/swf_parser.py` + `extract_all.py` to dump every bitmap symbol from `ability_icons.swf` (and `ui.swf` if needed) to PNG.
2. Stage selected symbols into `assets/icons/abilities/<symbolName>.png` via a script analogous to `stage_icons_to_assets.py`.
3. Also stage `type_icon` badges and `icon_shell_frame` shells (locations to be discovered during extraction — may be in `ui.swf`).
4. Commit the PNGs. The extraction scripts stay under `defect-investigation/` and are dev-only.

### Phase 2 — Build the ability → icon map
1. Parse every `data/abilities/*.gon` once at app startup (or pre-bake to JSON):
   - For each ability block, record block key (ability name) and `graphics.animation`.
   - If `meta.ability_icon` is present, that overrides the animation value.
   - Also record `type_icon` and `icon_shell_frame` for composite rendering.
2. Resolve override chains (one hop) so each ability has a final symbol name.
3. Persist as `assets/ability_icon_map.json` checked in alongside the PNGs.

### Phase 3 — Disorder icons (separate investigation)
1. Inspect `catparts.swf` symbol list (via the existing SWF extractor).
2. Determine the `(mutation_slot, mutation_id)` → symbol convention (likely ties into `visual_mutation_catalog.py`).
3. Stage the needed sprites into `assets/icons/disorders/` and build `assets/disorder_icon_map.json`.

### Phase 4 — Display in app
1. Add `IconProvider` in `src/breed_priority/` that takes `ability_name` or `(slot, mutation_id)` and returns a `QPixmap`, cached via `QPixmapCache`. Generic fallback pixmap when missing (mirroring `visual_mutation_catalog.py`'s fallback pattern).
2. Render in `tooltips.py` (HTML tooltips can embed `<img>` from a temp data URL or local file path) and any ability/mutation chip widgets.
3. Resolve `assets/` path robustly under both `python src/mewgenics_manager.py` and the PyInstaller `.exe` build (`sys._MEIPASS`).

## Build implications

- `build.bat` / PyInstaller spec must bundle `assets/` as a data directory.
- `.editorconfig` and existing UTF-8/LF conventions still apply to any new JSON map files.

## Open questions

- **Pre-composite vs. layer at render time**: pre-render icon+shell+type-badge into a single PNG per ability (simpler runtime, more files), or layer the three in Qt (fewer files, slightly more code)?
- **Disorder icon scope**: cat-part sprites for every (slot, id), or defer Phase 3 and stick with text/emoji for v1?
- **Icon size**: pick one canonical size at extraction time (e.g. 48×48 or 64×64), or store at source resolution and scale in Qt?
