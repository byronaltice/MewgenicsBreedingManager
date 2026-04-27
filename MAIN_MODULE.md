# MAIN_MODULE.md

The following information is only needed if it supports Breed Priority. Do not automatically assume that anything in the subsections applies to breed priority. Prefer the information in the Breed Priority Module section above instead, but use the below information to understand how Mewgenics Manager hands off data and functionality to Breed Priority, inspiration on how to parse the save file, etc. Assume that whoever wrote Mewgenics Manager has no knowledge of Breed Priority. The only updates within Mewgenics Manager that are Breed Priority aware were created by the person who made Breed Priority.

Assume that, in the future, Breed Priority will become a standalone module. Other functionality within Mewgenics Manager, except where it supports Breed Priority, will be removed.

## Data Flow

1. User selects a `.sav` file -> `SaveLoadWorker` calls `parse_save()` -> `Cat` objects created
2. Parent/child links resolved by UID matching + blob scanning fallback
3. Generation depth computed iteratively (gen 0 = no parents)
4. `BreedingCache` pre-computes all pair outcomes in a background thread
5. `QFileSystemWatcher` triggers auto-refresh when the save file changes on disk

## `save_parser.py` — Core Data Layer

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

## `breeding.py` — Breeding Logic

No Qt dependencies.

- **`PairProjection`**: Expected offspring stat ranges for a pair.
- **`PairFactors`**: Full score breakdown (risk, complementarity, personality bonus, etc.).
- **`pair_projection(cat_a, cat_b) -> PairProjection`**: Offspring stat projections.
- **`score_pair(cat_a, cat_b) -> PairFactors`**: Scores a pair on all axes.
- `is_mutual_lover_pair`, `planner_pair_allows_breeding`, `planner_inbreeding_penalty`, `planner_pair_bias`: Planner compatibility checks.
- `tracked_offspring`: Offspring tracked for a pair in the planner.

## `room_optimizer/` — Room Assignment

Greedy optimizer that assigns cats to rooms to maximize breeding outcomes.

- **`RoomType`** (enum): `BREEDING`, `FALLBACK`, `GENERAL`, `NONE`
- **`RoomConfig`**: Per-room settings (capacity, type, base stimulation).
- **`OptimizationParams`**: Solver config (min_stats, max_risk, stimulation threshold).
- **`optimize_room_distribution(cats, rooms, params) -> OptimizationResult`**: Main solver entry point.
- `parallel.py`: Parallel simulated annealing variant — operates on serializable primitives only.

## `mewgenics/` — Qt UI Package

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

## Known Design Decisions

- **Lover conflicts at room level, not pair level**: `breeding.py::is_lover_conflict()` intentionally returns `False`. Lover exclusivity is enforced at room assignment time by `room_optimizer/optimizer.py::_filter_lover_exclusivity()`.
- **Generation depth fallback**: Cats with unresolvable ancestry default to generation 0 (stray). The iterative algorithm in `parse_save()` converges; the fallback is intentional.
- **Inbredness/sexuality dual field**: During `Cat.__init__`, `inbredness` temporarily holds the raw sexuality float. It is overwritten with true COI in `MainWindow._on_save_loaded()`. `parsed_inbredness` preserves the original for calibration override detection.
- **Cross-class access**: Views expose public properties/methods (`room_priority_panel`, `cat_locator`, `offspring_tracker`, `set_navigate_to_cat_callback()`, `save_session_state()`) for MainWindow to use. Avoid accessing `_private` attributes across class boundaries.
- **Module-level initialization**: `mewgenics/__init__.py` runs setup (game data, locale, tags, thresholds) once when the package is first imported. Modules that need initialized state import it after this runs.
