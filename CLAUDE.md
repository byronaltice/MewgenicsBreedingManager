# CLAUDE.md

## Project Overview

PySide6 desktop app that reads Mewgenics save files and provides breeding management tools. Parses binary `.sav` files (LZ4-compressed SQLite) to extract cat data (stats, abilities, mutations, relationships, lineage) and displays it across 12+ specialized views.

## Build & Run

```bash
pip install -r requirements.txt
python src/mewgenics_manager.py

# Build standalone Windows exe
build.bat
```

No test suite or linter. Testing is manual through the GUI.

## Module Structure

All source lives under `src/`. Entry point is `src/mewgenics_manager.py`.

```
src/
  mewgenics_manager.py          # Qt UI layer — all views, MainWindow, workers (~19k lines)
  save_parser.py                # Binary parser, Cat model, genetics/kinship logic
  breeding.py                   # Breeding compatibility, scoring, offspring tracking
  room_optimizer/
    types.py                    # Dataclasses: RoomConfig, OptimizationParams, ScoredPair, etc.
    optimizer.py                # Room assignment algorithm
  visual_mutation_catalog.py    # Lookup tables: (slot, mutation_id) → display name
```

### `save_parser.py` — Core Data Layer

Everything that touches the binary save format or genetic math lives here. No Qt dependencies.

- **`BinaryReader`**: Stateful binary reader (u32, u64, f64, utf16str, etc.)
- **`Cat`**: Core data model. Holds stats, abilities, mutations, relationships, room assignment, generation depth.
- **`SaveData`**: Container for a fully-parsed save (cats list + metadata).
- **`GameData`**: Lookup tables for visual mutations and furniture definitions. Populated at startup from `.gpak` files.
- **`FurnitureItem / FurnitureDefinition / FurnitureRoomSummary`**: Furniture parsing and room stat aggregation.
- **`parse_save(path) → (cats, errors)`**: Top-level entry point. Constructs Cat objects, resolves parent/child links, computes generation depths.
- `can_breed`, `risk_percent`, `kinship_coi`, `raw_coi`, `shared_ancestor_counts`: Breeding eligibility and kinship math.

Key constants:
- `STAT_NAMES = ["STR", "DEX", "CON", "INT", "SPD", "CHA", "LCK"]` — 7 stats, max value 7
- `EXCEPTIONAL_SUM_THRESHOLD = 40`, `DONATION_SUM_THRESHOLD = 34`, `DONATION_MAX_TOP_STAT = 6`
- Generation: `0` = stray (no parents in save), `1+` = bred kitten

### `breeding.py` — Breeding Logic

No Qt dependencies.

- **`PairProjection`**: Expected offspring stat ranges for a pair.
- **`PairFactors`**: Full score breakdown (risk, complementarity, personality bonus, etc.).
- **`pair_projection(cat_a, cat_b) → PairProjection`**: Offspring stat projections.
- **`score_pair(cat_a, cat_b) → PairFactors`**: Scores a pair on all axes.
- `is_mutual_lover_pair`, `planner_pair_allows_breeding`, `planner_inbreeding_penalty`, `planner_pair_bias`: Planner compatibility checks.
- `tracked_offspring`: Offspring tracked for a pair in the planner.

### `room_optimizer/` — Room Assignment

Greedy optimizer that assigns cats to rooms to maximize breeding outcomes.

- **`RoomType`** (enum): `BREEDING`, `FALLBACK`, `GENERAL`, `NONE`
- **`RoomConfig`**: Per-room settings (capacity, type, base stimulation).
- **`OptimizationParams`**: Solver config (min_stats, max_risk, stimulation threshold).
- **`optimize_room_distribution(cats, rooms, params) → OptimizationResult`**: Main solver entry point.

### `mewgenics_manager.py` — Qt UI Layer

Imports from `save_parser`, `breeding`, and `room_optimizer`. All PySide6 code lives here.

Workers:
- **`SaveLoadWorker(QThread)`**: Async save parsing.
- **`BreedingCache / BreedingCacheWorker`**: Pre-computes all pair outcomes in background.
- **`RoomOptimizerWorker(QThread)`**: Runs room assignment solver off the main thread.
- **`QuickRoomRefreshWorker(QThread)`**: Background room-data refresh.

Views:
- `MainWindow` — QMainWindow hub, owns all views via QTabWidget
- `CatTableModel` — sortable/filterable roster table
- `CatDetailPanel` — stat/trait detail for a selected cat
- `SafeBreedingView` — safe breeding partners for a selected cat
- `BreedingPartnersView` — pair compatibility grid
- `FamilyTreeBrowserView` — visual ancestry tree
- `LineageDialog` — modal lineage/pedigree viewer
- `RoomOptimizerView` — room assignment UI backed by `room_optimizer`
- `PerfectCatPlannerView` — multi-generation breeding planner
- `CalibrationView` — parser field calibration (dev use)
- `MutationDisorderPlannerView` — mutation/disorder targeting planner
- `FurnitureView` — furniture stat viewer per room
- `SaveSelectorDialog` — initial save file picker

## Data Flow

1. User selects a `.sav` file → `SaveLoadWorker` calls `parse_save()` → `Cat` objects created
2. Parent/child links resolved by UID matching + blob scanning fallback
3. Generation depth computed iteratively (gen 0 = no parents)
4. `BreedingCache` pre-computes all pair outcomes in a background thread
5. `QFileSystemWatcher` triggers auto-refresh when the save file changes on disk

## Conventions

- Windows-targeted: save paths use `%LOCALAPPDATA%`, build produces `.exe`
- Qt signals/slots for all UI reactivity; `blockSignals(True)` prevents cascading updates during programmatic changes
- Views persist user choices to a JSON sidecar file alongside the save (load on `__init__`, save on every change)

## Known Design Decisions

- **Lover conflicts at room level, not pair level**: `breeding.py::is_lover_conflict()` intentionally returns `False`. Lover exclusivity is enforced at room assignment time by `room_optimizer/optimizer.py::_filter_lover_exclusivity()`.
- **Generation depth fallback**: Cats with unresolvable ancestry default to generation 0 (stray). The iterative algorithm in `parse_save()` converges; the fallback is intentional.
- **Inbredness/sexuality dual field**: During `Cat.__init__`, `inbredness` temporarily holds the raw sexuality float. It is overwritten with true COI in `MainWindow._on_save_loaded()`. `parsed_inbredness` preserves the original for calibration override detection.
- **Cross-class access**: Views expose public properties/methods (`room_priority_panel`, `cat_locator`, `offspring_tracker`, `set_navigate_to_cat_callback()`, `save_session_state()`) for MainWindow to use. Avoid accessing `_private` attributes across class boundaries.

## tools/field_mapper/

Reverse-engineering pipeline for discovering binary field offsets. Dev-only — not part of the main app.
