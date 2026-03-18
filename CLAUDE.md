# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PySide6 desktop app that reads Mewgenics save files and provides breeding management tools. Parses binary `.sav` files (LZ4-compressed) to extract cat data (stats, abilities, mutations, relationships, lineage) and displays it across 12+ specialized views.

## Build & Run

```bash
# Install dependencies
pip install -r requirements.txt   # PySide6, lz4

# Run the app
python mewgenics_manager.py

# Build standalone Windows exe (PyInstaller)
build.bat
```

No test suite or linter is configured. Testing is manual through the GUI.

## Architecture

### Core Modules

- **`mewgenics_manager.py`** (~11k lines): Monolithic main file containing the binary parser, Cat data model, all UI views, and the main window. Entry point.
- **`visual_mutation_catalog.py`**: Lookup tables mapping `(slot, mutation_id)` tuples to display names for visual mutations and birth defects.

### Key Classes (in mewgenics_manager.py)

- **`BinaryReader`**: Stateful reader for parsing the binary save format (u32, u64, f64, utf16str, etc.)
- **`Cat`**: Core data model. Constructed from a blob of bytes. Holds stats, abilities, mutations, relationships, generation depth, room assignment.
- **`parse_save(path)`**: Reads a `.sav` file, constructs all Cat objects, resolves parent/child links, computes generation depths. Returns `(cats, errors)`.
- **`MainWindow`**: QMainWindow hub coordinating all views. Uses QTabWidget for view switching.
- **`CatTableModel(QAbstractTableModel)`**: Powers the main sortable/filterable roster table.
- **`SaveLoadWorker(QThread)`**: Async save loading to keep UI responsive.
- **`BreedingCache / BreedingCacheWorker`**: Threaded pre-computation of breeding pair outcomes.

### Data Flow

1. User selects a `.sav` file → `SaveLoadWorker` parses binary via `BinaryReader` → `Cat` objects created
2. Parent/child relationships resolved by UID matching + blob scanning fallback
3. Generation depth computed iteratively (gen 0 = stray with no parents, gen 1+ = bred kittens)
4. `BreedingCache` pre-computes pair outcomes in a background thread
5. `QFileSystemWatcher` triggers auto-refresh when the save file changes on disk

### Save Persistence Pattern

Views that need to persist user choices save to a JSON sidecar file alongside the save. The path is derived from the save file path. Load happens in `__init__`, save happens on every user change.

### Important Constants

- **`STAT_NAMES`** = `["STR", "DEX", "CON", "INT", "SPD", "CHA", "LCK"]` — 7 stats, max value 7
- **Generation**: `0` = stray (no parents), `1+` = bred kitten (has parents in the save)
- **`EXCEPTIONAL_SUM_THRESHOLD`** = 40, **`DONATION_SUM_THRESHOLD`** = 34

## Conventions

- Windows-targeted (save paths use `%LOCALAPPDATA%`, build produces `.exe`)
- No formal module/package structure — flat file layout
- Qt signals/slots for all UI reactivity; `blockSignals(True)` used to prevent cascading updates during programmatic changes
- Styles are inline Qt stylesheet strings (dark theme, hex colors)
- `.editorconfig`: UTF-8, 4-space indents, LF line endings

## tools/field_mapper/

Reverse-engineering pipeline for discovering field offsets in the binary save format. Uses SQLite to track ingested saves and discovered mappings. Not part of the main app — used during development to calibrate the parser.
