# Ability & Disorder Icon Integration Plan

## Goal

Display each ability's and disorder's in-game icon in the Breed Priority UI (tooltips, chips), e.g. show the real "Blow Kiss" icon next to the ability name. Do **not** ship game-derived icon assets in the repo — extract from the user's local Mewgenics install on first launch.

## What we know

- **Ability icons** are MovieClip symbols inside `<game>/resources/gpak-video/swfs/ability_icons.swf` (some in `ui.swf`). The icon symbol name comes from `graphics.animation` in each ability's GON under `<game>/resources/gpak-text/data/abilities/*.gon`.
- **`meta.ability_icon`** overrides redirect to another ability's icon (~14 cases, e.g. `FetusSpit` → `Spit`).
- **`meta.type_icon`** + **`meta.icon_shell_frame`** are category badge + frame overlays.
- **Disorders/mutations** have no icon field in GON; sprites live in `catparts.swf`, keyed by `(slot, mutation_id)` — naming scheme still to confirm during Phase 3.
- **SWF sizes**: `ability_icons.swf` 2.2 MB, `catparts.swf` 6 MB, `ui.swf` 45 MB. Source files stay in the game install; only rendered PNGs are produced.
- **Existing tooling** (dev-only): `defect-investigation/scripts/extract-symbols/swf_parser.py`, `extract_all.py`, `extract_final_icons.py`, `stage_icons_to_assets.py`. These read `.swf` files directly — no gpak parsing involved.
- **Existing shipped assets**: `src/breed_priority/assets/symbols/` already contains 18 small stat/UI symbol PNGs (pre-shipped, unchanged by this plan).

## Strategy: per-user extraction on first launch

- App-managed asset dir: `%LOCALAPPDATA%\MewgenicsBreedingManager\assets\icons\`
  - `abilities/<symbolName>.png`
  - `disorders/<slot>_<mutationId>.png`
  - `ability_icon_map.json`, `disorder_icon_map.json`
- On app startup the icon subsystem checks for a manifest file (e.g. `assets/icons/.manifest.json` containing schema version + extraction timestamp). If missing or outdated → run extraction.
- Extraction needs the user's game install path. If unknown, show a file picker ("Locate your Mewgenics install — folder containing `resources.gpak`"). Persist the path in app settings (existing settings/QSettings mechanism — confirm location during implementation).
- All Phase 1–3 scripts run inside the app process, not as separate CLI tools — but they're packaged as importable modules so they can also be run manually for development.

## Plan

### Phase 1 — Ability icon extractor
1. New module `src/breed_priority/icon_extraction/` containing:
   - `swf_parser.py` — copied/adapted from `defect-investigation/scripts/extract-symbols/swf_parser.py` (drop dev-only paths, keep pure parser).
   - `extract_abilities.py` — given a game install path, parses `ability_icons.swf` (and `ui.swf` for any missing symbols) and writes PNGs to `<assets>/icons/abilities/`.
   - `gon_ability_map.py` — parses every `<game>/resources/gpak-text/data/abilities/*.gon`, records `name → graphics.animation` (with `meta.ability_icon` override resolution + `type_icon` / `icon_shell_frame`), writes `<assets>/icons/ability_icon_map.json`.
2. Composition decision deferred to runtime: store base icon, type-badge, and shell as separate PNGs and let Qt layer them. (Avoids re-extraction if styling changes.)

### Phase 2 — App integration
1. New module `src/breed_priority/icon_provider.py`:
   - `ensure_assets_ready()` — called at app startup; checks manifest, prompts for game install if needed, runs extractor with progress dialog.
   - `get_ability_icon(ability_name) -> QPixmap` — cached via `QPixmapCache`; falls back to a generic placeholder PNG (shipped in `src/breed_priority/assets/symbols/` so the app always has *something*).
   - `get_disorder_icon(slot, mutation_id) -> QPixmap` — same pattern.
2. Wire into `tooltips.py` (HTML `<img src="file:///…">`) and any ability/mutation chip widgets.
3. Settings: persist game install path. Add a menu item "Re-extract icons…" for forcing a refresh.

### Phase 3 — Disorder icons (follow-up)
1. Inspect `catparts.swf` symbol list via the SWF parser.
2. Determine `(mutation_slot, mutation_id)` → symbol convention (cross-reference with `visual_mutation_catalog.py`).
3. Add `extract_disorders.py` + `gon_disorder_map.py` mirroring Phase 1.

### Phase 4 — Polish
- Progress dialog during extraction (cancellable).
- Logging: write extraction errors to `<assets>/icons/extraction.log` so missing symbols are debuggable.
- `build.bat` / PyInstaller spec change: bundle only the placeholder PNGs from `src/breed_priority/assets/symbols/`; do **not** include game-derived icons.
- "Re-extract icons…" menu item.

## Repo impact

- No game-derived PNGs committed.
- New code: `src/breed_priority/icon_extraction/` (~3–5 small files) and `icon_provider.py`.
- One small placeholder PNG added to `src/breed_priority/assets/symbols/` as the missing-icon fallback (if not already present).

## Open questions

- **Pre-composite vs. Qt layer**: plan currently picks Qt-layer; revisit if compositing perf is bad in tooltips.
- **Disorder icon scope for v1**: defer (Phase 3) — ship Phase 1+2 first.
- **Canonical extract size**: extract at native SWF resolution, scale in Qt — avoids re-extraction if UI scale changes.
- **Settings storage location for game install path**: confirm whether existing app uses `QSettings`, a JSON file in `%LOCALAPPDATA%`, or something else, and match it.
