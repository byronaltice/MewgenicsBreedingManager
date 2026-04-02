# CLAUDE.md

## Project Overview

PySide6 desktop app that reads Mewgenics save files and provides breeding management tools. Parses binary `.sav` files (LZ4-compressed SQLite) to extract cat data (stats, abilities, mutations, relationships, lineage) and displays it across 12+ specialized views.

## Build & Run

```bash
pip install -r requirements.txt
python src/mewgenics_manager.py

# Run tests
pytest

# Build standalone Windows exe
build.bat
```

## Module Structure

Entry point is `src/mewgenics_manager.py` (thin wrapper that calls `mewgenics.app.main()`). All application code lives in the `src/mewgenics/` package.

```
src/
  mewgenics_manager.py              # Backwards-compatible entry point (thin wrapper)
  save_parser.py                    # Binary parser, Cat model, genetics/kinship logic
  breeding.py                       # Breeding compatibility, scoring, offspring tracking
  breed_priority.py                 # BreedPriorityView widget and orchestration
  breed_priority_constants.py       # Shared constants, styles, and column indices
  breed_priority_scoring.py         # Score computation helpers for breed priority
  breed_priority_delegates.py       # Custom Qt delegates and controls for score table
  breed_priority_filters.py         # Breed priority filter dialog and state
  room_optimizer/
    types.py                        # Dataclasses: RoomConfig, OptimizationParams, ScoredPair, etc.
    optimizer.py                    # Room assignment algorithm
  visual_mutation_catalog.py        # Lookup tables: (slot, mutation_id) -> display name
  mewgenics/
    __init__.py                     # Package init + module-level setup (locale, tags, thresholds)
    app.py                          # main() — QApplication, palette, save selector
    main_window.py                  # MainWindow (~3000 lines)
    constants.py                    # Colors, column indices, widths, stylesheets
    dialogs.py                      # TagManagerDialog, ThresholdPreferencesDialog,
                                    #   SharedOptimizerSearchSettingsDialog, SaveSelectorDialog
    panels/
      cat_detail.py                 # CatDetailPanel, LineageDialog, chip helpers
      room_priority.py              # RoomPriorityPanel
    models/
      breeding_cache.py             # BreedingCache + BreedingCacheWorker
      cat_table_model.py            # CatTableModel, NameTagDelegate, sort helpers
      room_filter_model.py          # RoomFilterModel
    workers/
      save_loader.py                # SaveLoadWorker
      room_refresh.py               # QuickRoomRefreshWorker
      optimizer_worker.py           # RoomOptimizerWorker
    views/
      family_tree.py                # FamilyTreeBrowserView
      safe_breeding.py              # SafeBreedingView
      breeding_partners.py          # BreedingPartnersView
      room_optimizer.py             # RoomOptimizerView, RoomOptimizerCatLocator, RoomOptimizerDetailPanel
      perfect_planner.py            # PerfectCatPlannerView + 4 sub-panels
      calibration.py                # CalibrationView
      mutation_planner.py           # MutationDisorderPlannerView + planner trait helpers
      furniture.py                  # FurnitureView
    utils/
      paths.py                      # Bundle dir, save dir, gpak paths, file finders
      config.py                     # App config load/save, UI state, splitter persistence
      localization.py               # _tr(), locale catalog, language management
      styling.py                    # Font enforcement, widget styling, _chip(), _sec()
      tags.py                       # Tag definitions, icons, pixmaps
      thresholds.py                 # Breeding threshold preferences
      optimizer_settings.py         # Optimizer flags, search settings, room priority config
      planner_state.py              # Planner blob persistence, foundation pairs
      game_data.py                  # GPAK loading, game data reload
      calibration.py                # Calibration data load/save, trait overrides
      cat_persistence.py            # Blacklist, must-breed, pinned, tags load/save
      cat_analysis.py               # _cat_base_sum, exceptional/donation checks
      abilities.py                  # Ability/mutation descriptions, tooltips, effect lines
      table_state.py                # Table view header/sort state persistence
```

### Breed Priority Column Layout

The score table uses thin separator columns (`_SEP_HEADER = "│"`) as visual dividers:

```
Name | Loc | Inj | STR..LCK | [SEP1] | Sum..Trait | [SEP2] | Score
 0      1     2    3..9        10       11..26       27       28
```

Use constants and avoid hard-coded indices:
- `COL_SEP1`, `_COL_SCORE_START`, `COL_SEP2`, `COL_SCORE`
- `_SEP_COLS = frozenset({COL_SEP1, COL_SEP2})` for guard checks

When column count changes, invalidate saved width maps using a persisted `col_count` stamp in the sidecar state.

### Breed Priority Display Mode and Heatmap

- `self._display_mode` supports `"score" | "values" | "both"` and controls text format in scored columns.
- `self._heatmap_on` is independent and overlays bars on any display mode.
- `_BothModeDelegate` handles plain text, both-mode subscript rendering, and heatmap bar overlay.
- Column widths persist per display mode (`self._col_widths`), not per profile.

### `save_parser.py` — Core Data Layer

Everything that touches the binary save format or genetic math lives here. No Qt dependencies.

- **`BinaryReader`**: Stateful binary reader (u32, u64, f64, utf16str, etc.)
- **`Cat`**: Core data model. Holds stats, abilities, mutations, relationships, room assignment, generation depth.
- **`SaveData`**: Container for a fully-parsed save (cats list + metadata).
- **`GameData`**: Lookup tables for visual mutations and furniture definitions. Populated at startup from `.gpak` files.
- **`FurnitureItem / FurnitureDefinition / FurnitureRoomSummary`**: Furniture parsing and room stat aggregation.
- **`parse_save(path) -> (cats, errors)`**: Top-level entry point. Constructs Cat objects, resolves parent/child links, computes generation depths.
- `can_breed`, `risk_percent`, `kinship_coi`, `raw_coi`, `shared_ancestor_counts`: Breeding eligibility and kinship math.

Key constants:
- `STAT_NAMES = ["STR", "DEX", "CON", "INT", "SPD", "CHA", "LCK"]` — 7 stats, max value 7
- `EXCEPTIONAL_SUM_THRESHOLD = 40`, `DONATION_SUM_THRESHOLD = 34`, `DONATION_MAX_TOP_STAT = 6`
- Generation: `0` = stray (no parents in save), `1+` = bred kitten

### `breeding.py` — Breeding Logic

No Qt dependencies.

- **`PairProjection`**: Expected offspring stat ranges for a pair.
- **`PairFactors`**: Full score breakdown (risk, complementarity, personality bonus, etc.).
- **`pair_projection(cat_a, cat_b) -> PairProjection`**: Offspring stat projections.
- **`score_pair(cat_a, cat_b) -> PairFactors`**: Scores a pair on all axes.
- `is_mutual_lover_pair`, `planner_pair_allows_breeding`, `planner_inbreeding_penalty`, `planner_pair_bias`: Planner compatibility checks.
- `tracked_offspring`: Offspring tracked for a pair in the planner.

### `room_optimizer/` — Room Assignment

Greedy optimizer that assigns cats to rooms to maximize breeding outcomes.

- **`RoomType`** (enum): `BREEDING`, `FALLBACK`, `GENERAL`, `NONE`
- **`RoomConfig`**: Per-room settings (capacity, type, base stimulation).
- **`OptimizationParams`**: Solver config (min_stats, max_risk, stimulation threshold).
- **`optimize_room_distribution(cats, rooms, params) -> OptimizationResult`**: Main solver entry point.

### `mewgenics/` — Qt UI Package

All PySide6 code lives here. `mewgenics/__init__.py` runs one-time initialization (locale, tags, thresholds, game data).

**Key modules:**
- **`main_window.py`** — `MainWindow` (QMainWindow hub, owns all views via QTabWidget)
- **`app.py`** — `main()` entry point (QApplication setup, palette, save selector)
- **`dialogs.py`** — All dialog windows (tag manager, threshold prefs, optimizer settings, save selector)
- **`panels/cat_detail.py`** — `CatDetailPanel` (stat/trait detail for selected cat) + `LineageDialog`
- **`panels/room_priority.py`** — `RoomPriorityPanel` (room priority configuration)

**Views** (each is a self-contained tab):
- `views/family_tree.py` — `FamilyTreeBrowserView` (visual ancestry tree)
- `views/safe_breeding.py` — `SafeBreedingView` (safe breeding partners)
- `views/breeding_partners.py` — `BreedingPartnersView` (pair compatibility grid)
- `views/room_optimizer.py` — `RoomOptimizerView` + detail panel + cat locator
- `views/perfect_planner.py` — `PerfectCatPlannerView` + 4 sub-panels
- `views/calibration.py` — `CalibrationView` (parser field calibration, dev use)
- `views/mutation_planner.py` — `MutationDisorderPlannerView` (mutation/disorder targeting)
- `views/furniture.py` — `FurnitureView` (furniture stat viewer per room)

**Models & Workers:**
- `models/cat_table_model.py` — `CatTableModel`, `NameTagDelegate`
- `models/room_filter_model.py` — `RoomFilterModel`
- `models/breeding_cache.py` — `BreedingCache`, `BreedingCacheWorker`
- `workers/save_loader.py` — `SaveLoadWorker`
- `workers/room_refresh.py` — `QuickRoomRefreshWorker`
- `workers/optimizer_worker.py` — `RoomOptimizerWorker`

### Circular Import Prevention

`breeding.py`, `breed_priority.py`, `breed_priority_constants.py`, `breed_priority_scoring.py`, `breed_priority_delegates.py`, and `breed_priority_filters.py` are intentionally standalone and should not import from `mewgenics_manager.py`. Inject game-specific data via parameters.

## Data Flow

1. User selects a `.sav` file -> `SaveLoadWorker` calls `parse_save()` -> `Cat` objects created
2. Parent/child links resolved by UID matching + blob scanning fallback
3. Generation depth computed iteratively (gen 0 = no parents)
4. `BreedingCache` pre-computes all pair outcomes in a background thread
5. `QFileSystemWatcher` triggers auto-refresh when the save file changes on disk

## Standing Development Rules

- Prefer extending existing systems over introducing parallel implementations.
- Use semantic, role-based naming for shared styles and constants.
- Do not hard-code derived values or descriptions from parsed save data.
- If parsed data exists but lookup text is missing, use a generic fallback text.
- Keep completion reports focused on what changed, why, and notable risks.

## Testing

Tests live in `tests/` and run with `pytest` from the repo root.

Coverage includes parser, donation logic, cat detail views, UI persistence, room optimizer, perfect planner, trait labels, and visual helpers.

## Git

- Do not add `Co-Authored-By` lines.
- Only commit when asked; only push when asked.
- When amending, use `--date=now`.
- **Commit message style**: Describe what the program *does* differently — the behavior changed, feature added, or bug fixed. Omit low-level technical details that don't affect behavior. For purely technical changes (refactoring, style consolidation, test restructuring), use a high-level functional description: e.g. "Consolidated styles to increase modularity" rather than "Added _SOME_VAR to breed_priority.py, replacing _SOME_OTHER_VAR".

## Conventions

- Windows-targeted: save paths use `%LOCALAPPDATA%`, build produces `.exe`
- Qt signals/slots for all UI reactivity; `blockSignals(True)` prevents cascading updates during programmatic changes
- Styles are inline Qt stylesheet strings (dark theme, hex colors)
- `.editorconfig`: UTF-8, 4-space indents, LF line endings
- Views persist user choices to a JSON sidecar file alongside the save (load on `__init__`, save on every change)
- Utility modules use `_` prefix convention — functions are module-private but importable across the package
- Mutable module-level state (dicts, lists) must use in-place mutation (`.clear()` + `.update()`, slice assignment) when shared across modules, not rebinding
- Internationalization via locale JSON files in `locales/` (en, ru, zh_CN, pl)
- Version string is managed in `VERSION` at repo root

**Autonomy scope:** Free to move, rename, delete, and restructure files within the repo. Cautious with irreversible actions outside the repo (destructive OS-level operations). Git operations are generally safe — committed code is recoverable from reflog.

## Code Quality

Apply these rules to all code you write or modify. When the explicit purpose of a session is refactoring, these rules are the goal — apply them fully.

**Concrete rules:**
- No magic numbers — every numeric literal except `0`, `1`, and trivially obvious arithmetic (e.g., `len(x) - 1`) must be a named constant
- New UI values (colors, sizes, column indices, widths) belong in `constants.py`; user-facing strings go through `_tr()`
- Meaningful names — no `data`, `result`, `tmp`, `val`, or single-letter names outside of loop counters (`i`, `j`, `k`)
- One responsibility per function — if describing it requires "and", split it
- Repeated string literals used as keys, identifiers, or config values belong in constants

**Structural judgment:**
- Match abstraction level to complexity — don't wrap a 3-line utility in a class, but don't write 300-line procedural functions either
- Low coupling — modules communicate through public APIs and Qt signals, not by reaching into each other's internals
- Reuse before creating — before adding a new helper, class, or pattern, search for an existing one to reuse or extend
- DRY — don't duplicate logic; extract shared behavior into a common location
- Keep abstraction levels consistent within a function — don't mix high-level orchestration with low-level implementation details in the same function body
- Before modifying a module, read it and match its style and patterns; extend existing patterns rather than inventing new ones
- Fix the class of issues, not just the instance — when fixing one violation, search for similar ones nearby

**Judgment over dogma:** If following a rule makes the code demonstrably worse in context, note the deviation briefly.

## Known Design Decisions

- **Lover conflicts at room level, not pair level**: `breeding.py::is_lover_conflict()` intentionally returns `False`. Lover exclusivity is enforced at room assignment time by `room_optimizer/optimizer.py::_filter_lover_exclusivity()`.
- **Generation depth fallback**: Cats with unresolvable ancestry default to generation 0 (stray). The iterative algorithm in `parse_save()` converges; the fallback is intentional.
- **Inbredness/sexuality dual field**: During `Cat.__init__`, `inbredness` temporarily holds the raw sexuality float. It is overwritten with true COI in `MainWindow._on_save_loaded()`. `parsed_inbredness` preserves the original for calibration override detection.
- **Cross-class access**: Views expose public properties/methods (`room_priority_panel`, `cat_locator`, `offspring_tracker`, `set_navigate_to_cat_callback()`, `save_session_state()`) for MainWindow to use. Avoid accessing `_private` attributes across class boundaries.
- **Module-level initialization**: `mewgenics/__init__.py` runs setup (game data, locale, tags, thresholds) once when the package is first imported. Modules that need initialized state import it after this runs.

## tools/field_mapper/

Reverse-engineering pipeline for discovering binary field offsets. Dev-only — not part of the main app.
