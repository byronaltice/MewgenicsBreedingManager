# Mewgenics Breeding Manager

An external breeding and roster manager for [Mewgenics](https://store.steampowered.com/app/686060/Mewgenics/) — similar to Dwarf Therapist for Dwarf Fortress.

Reads your save file live and gives you a clear view of every cat's stats, room, abilities, mutations, and lineage so you can make smarter breeding decisions without alt-tabbing.

> **Note:** This tool was vibecoded. The family tree and inbreeding analysis features are not guaranteed to be accurate. They can be enabled via **Settings → Show Family Tree & Inbreeding** (off by default).

## Screenshots

### Single Cat View
![Single Cat View](Sceenshots/Single%20Cat%20View.png)

The main roster table showing all alive cats with color-coded base stats (red → grey → green), abilities, mutations, and a **Risk%** column indicating inbreeding risk relative to the selected cat. Clicking any row opens the detail panel at the bottom, showing the cat's abilities, lineage (parents and grandparents), and room assignment.

### Breeding Comparison View
![Breeding Cats View](Sceenshots/Breeding%20Cats%20View.png)

Ctrl+click two compatible cats to enter breeding comparison mode. The detail panel shows each cat's stats side-by-side and calculates the **offspring stat ranges** (min–max per stat and total sum range). Both cats' abilities are listed so you can plan which traits will carry forward.

### Family Tree View
![Family Tree View](Sceenshots/Family%20Tree%20View.png)

Select a cat from the list and switch to **Family Tree View** in the sidebar to see a visual generational tree: the selected cat at the top (SELF), their children in the row below, and grandchildren below that. Each box shows the cat's name, gender, and current room or Gone status. Click any box to jump to that cat.

### Safe Breeding View
![Safe Breeding](Sceenshots/Safe%20Breeding.png)

The **Safe Breeding** panel ranks all viable alive partners for the selected cat by ascending inbreeding risk. Columns show **Risk%** (normalized Wright's Coefficient of Inbreeding), **Shared Ancestors** count, and a plain-language label — *Not Inbred*, *Slightly Inbred*, *Moderately Inbred*, etc. — so you can immediately pick the safest pairing.

## Features

- **Live save reading** — watches the save file and reloads automatically when the game writes
- **Full cat roster** — all cats in one sortable table; filter by room, adventure, or gone (with counts)
- **Color-coded base stats** — red (1) → grey (4) → green (7) at a glance
- **Detail panel** — click any cat to see abilities, mutations, and lineage; hover chips for descriptions
- **Breeding comparison** — Ctrl+click two cats to see offspring stat ranges and combined mutations
- **Search bar** — filter cats by name in real time
- **Family tree & inbreeding** (optional) — toggle in Settings; shows Gen depth, Source column, inbreeding score, shared-ancestor warnings, and risky-pair lowlighting
- **Risk% column** — inbreeding risk percentage for every cat relative to the selected one, using Wright's Coefficient of Inbreeding
- **Safe Breeding view** — sidebar panel that ranks all valid alive partners for a selected cat by ascending risk, with shared ancestor counts and plain-language labels
- **Family Tree view** — visual generational tree (self → children → grandchildren) with click-to-navigate boxes
- **UI zoom** — Ctrl+= / Ctrl+- / Ctrl+0 to scale the entire interface from 70%–200%

## Requirements

- Python 3.11+
- [PySide6](https://pypi.org/project/PySide6/)
- [lz4](https://pypi.org/project/lz4/)

## Installation

```bash
git clone https://github.com/frankieg33/MewgenicsBreedingManager
cd MewgenicsBreedingManager
pip install -r requirements.txt
python mewgenics_manager.py
```

Or on Windows, double-click **build.bat** to build a standalone `.exe` via PyInstaller.

## Usage

The app auto-detects your save file from:
```
%APPDATA%\Glaiel Games\Mewgenics\<SteamID>\saves\
```

Use **File → Open Save File** to load a different save, or **File → Reload** (F5) to force a refresh.

### Roster table
| Column | Description |
|--------|-------------|
| Name | Cat's name |
| ♀/♂ | Gender |
| Room | Current room in the house |
| Status | `House` / `Away` (adventure) / `Gone` |
| STR–LCK | Base (heritable) stats, color coded |
| Sum | Sum of all base stats |
| Abilities | Active abilities |
| Mutations | Passive mutation traits |
| Gen / Source / Inbr | Lineage columns (visible when toggled on) |
| Risk% | Inbreeding risk vs. selected cat (visible when toggled on) |

Hover a stat cell to see base vs. total (including equipment bonuses).
Hover an ability or mutation chip to see what it does.

### Detail panel
- **1 cat selected** — shows abilities, mutations, equipment, and known lineage
- **2 cats selected (Ctrl+click)** — shows a breeding comparison with per-stat offspring ranges and combined mutations

### Sidebar filters
- **All Cats** — every cat including gone
- **Alive** — in house + adventure cats
- **Room buttons** — dynamically generated for each occupied room (with cat counts)
- **On Adventure** — cats currently in a run
- **Gone** — dead/sold cats

### Safe Breeding view
Click **Safe Breeding** in the sidebar to open the partner-ranking panel for the selected alive cat. It shows only valid breeding candidates (opposite or compatible sex, alive) sorted safest-first:

| Column | Description |
|--------|-------------|
| Cat | Partner name and gender |
| Risk% | Estimated inbreeding risk for offspring |
| Shared Anc. | Number of common ancestors found in lineage |
| Children will be | Plain-language risk label |

Risk labels:
- **Not Inbred** — 0–19%
- **Slightly Inbred** — 20–49%
- **Moderately Inbred** — 50–99%
- **Highly Inbred** — 100% (capped)

Clicking a row switches focus to that cat in the main roster.

### UI zoom
Adjust the interface scale under **Settings** or with keyboard shortcuts:

| Action | Shortcut |
|--------|----------|
| Zoom In | Ctrl+= or Ctrl++ |
| Zoom Out | Ctrl+- |
| Reset Zoom | Ctrl+0 |

Scale range is 70%–200%. Font sizes are also enforced to stay accessible at any zoom level.

## How Inbreeding Risk is Calculated

Risk% is based on Wright's Coefficient of Inbreeding (CoI), computed from the ancestry paths of two potential breeding partners.

**1. Build ancestor data**
- `_ancestor_depths(cat)` — finds how many generations away each ancestor is
- `_ancestor_paths(cat)` — builds all unique upward paths from a cat to each ancestor; loops through the same cat are rejected

**2. Compute raw CoI**
For each common ancestor shared by Cat A and Cat B, every valid path combination is evaluated:
- Reject combinations that reuse the same cat on both sides (except the common ancestor itself)
- Each valid combination contributes: `0.5 ** (sa + sb + 1)`
  - `sa` = edges from A to the ancestor
  - `sb` = edges from B to the ancestor
- Closer shared ancestors contribute more weight; distant ones contribute less

**3. Convert to Risk%**
```
Risk% = clamp((raw_coi / 0.25) × 100, 0, 100)
```
A raw CoI of 0.25 (e.g. first-cousins) maps to 100%. Values above that are capped at 100%.

**4. Sorting in Safe Breeding**
- Primary: lower Risk% first
- Secondary tie-break: `recent_shared × 1000 + total_shared` (penalizes recent shared ancestry more heavily)
- Final tie-break: partner name alphabetically

## Notes

Parent links are resolved from the pedigree stored in the save file. The family tree and inbreeding features are experimental — they can be wrong, especially for cats with complex lineage or saves that have been running for a long time. Enable them via **Settings → Show Family Tree & Inbreeding**.

## Credits

Save file parsing based on [pzx521521/mewgenics-save-editor](https://github.com/pzx521521/mewgenics-save-editor) and community research on the Mewgenics save format.
