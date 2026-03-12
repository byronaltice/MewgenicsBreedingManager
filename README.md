# Mewgenics Breeding Manager

External roster, breeding, and planning tool for [Mewgenics](https://store.steampowered.com/app/686060/Mewgenics/).

It reads your save, shows the cats in a sortable live table, and adds planning views for safe breeding, room assignment, lineage, and long-term perfect-stat progression.

## What It Does

- Live-loads Mewgenics saves and refreshes when the save changes
- Shows all cats with base stats, abilities, mutations, relationships, and lineage context
- Compares breeding pairs with offspring stat ranges, inheritance odds, and breakpoint hints
- Parses lovers and haters and uses them in optimizer logic
- Loads ability and mutation descriptions from `resources.gpak` when available
- Helps plan toward perfect 7-base-stat lines with staged pairing guidance

## Main Features

### Main roster

![Home Screen](Sceenshots/Home%20Screen.png)

- Sortable and searchable table for your cats
- Click `BL` and `MB` cells directly to toggle breeding blacklist and must-breed priority
- `Risk%` can show inbreeding risk relative to the selected cat
- `[EXC]` exceptional breeder
- `[DON]` donation candidate

Current documented thresholds:

- Exceptional breeder: base stat sum `>= 40`
- Donation candidate heuristic:
  - base stat sum `<= 34`, and/or
  - top base stat `<= 6`, and/or
  - high aggression
  - must-breed and exceptional cats are excluded from donation marking

### Single-cat detail view

![Single Cat View](Sceenshots/Single%20Cat%20View.png)

- Base / mod / total stat grid
- Ability chips with inline effect descriptions
- Mutation chips with inline effect descriptions
- Equipment
- Parents / grandparents
- Lovers / haters
- Include-in-breeding and must-breed controls

### Breeding Comparison View

![Breeding Comparison View](Sceenshots/Breeding%20Cats%20View.png)

Select two compatible cats to open pair mode.

It shows:

- parent base stats
- offspring stat ranges
- inherited trait ranges
- ability / passive inheritance estimates
- stimulation-adjusted source weighting
- breakpoint hints:
  - locked 7s
  - stats that can hit 7 now
  - one-step-off stats
  - stalled stats
- appearance preview from parsed visual/body data

### Room Optimizer

![Room Optimizer](Sceenshots/Room%20Optimizer.png)

Optimizer for room placement and pair-quality planning.

Current controls include:

- minimum base stat sum
- maximum inbreeding risk
- mode toggle for pair quality vs family separation
- `Minimize Variance`
- `Avoid Lovers`
- `Prefer Low Aggression`
- `Prefer High Libido`

Current behavior includes:

- avoids hater conflicts
- can avoid lover conflicts
- prefers mutual lovers when appropriate
- uses parsed lovers / haters during placement
- shows per-room pair breakdowns with projected offspring ranges

### Perfect 7 Planner

![Perfect 7 Planner](Sceenshots/Perfect%207%20Planner.png)

Dedicated long-term planner for building perfect cats.

This is separate from the Room Optimizer because it plans across generations instead of just placing current cats into rooms.

Controls:

- minimum base stat sum
- maximum inbreeding risk
- number of starting pairs
- stimulation
- avoid lovers
- prefer low aggression
- prefer high libido

Output is staged:

1. foundation pairs to start with
2. child separation guidance
3. rotation / outcross guidance
4. finish-and-maintain guidance

Stage 1 and Stage 3 show pair grids with:

- parent stats
- offspring ranges
- expected values
- breakpoint-oriented reasoning

### Family Tree view

![Family Tree View](Sceenshots/Family%20Tree%20View.png)

Visual lineage browser for a selected cat.

Shows:

- self
- parents / grandparents
- children / grandchildren

### Safe Breeding view

![Safe Breeding](Sceenshots/Safe%20Breeding.png)

Ranks valid partners for the selected cat by breeding safety.

Shows:

- partner
- inbreeding risk
- shared ancestors
- plain-language inbreeding labels

### Breeding Partners View

![Breeding Partners](Sceenshots/Breeding%20Partners.png)

Dedicated view for mutual-lover pairs.

Useful for:

- seeing who is bonded
- spotting room mismatches
- keeping breeding partners together

### Exceptional Cats view

![Exceptional Cats](Sceenshots/Exceptional%20Cats.png)

Sidebar filter for viewing cats marked as exceptional breeders.

Threshold:

- base stat sum `>= 40`

### Donation Candidates view

![Donation Candidates](Sceenshots/Donation%20Candidates.png)

Sidebar filter for viewing cats marked as donation candidates.

Heuristic for donation marking:

- base stat sum `<= 34`, and/or
- top base stat `<= 6`, and/or
- high aggression
- must-breed and exceptional cats are excluded from donation marking

### Calibration view

![Calibration](Sceenshots/Calibration.png)

Per-save parser override editor for alive cats.

Can override:

- gender
- age
- aggression
- libido
- inbredness
- base stats

Also exposes parser-research fields such as:

- voice token
- pre-gender `u32` values

Supports:

- save
- reload
- export calibration JSON
- import calibration JSON

### Locations settings

`Settings -> Locations...` lets you inspect and change:

- game install folder / `resources.gpak`
- save root directory

The app first checks common Steam install paths, then other discovered locations, then prompts when it still cannot find the game data.

## Mutation / Ability Support

The app now parses and displays:

- active abilities
- passive abilities
- visual mutations
- relationship data

When `resources.gpak` is available, it also loads:

- ability descriptions
- passive descriptions
- mutation descriptions

The visual mutation parser uses slot-aware extraction rather than the old generic placeholder approach, so mutation output should now match the game much more closely.

## Save / Parser Notes

The parser currently includes support for:

- room / alive / gone state
- parents and child links
- lovers / haters
- visual mutation slots
- personality fields:
  - aggression
  - libido
  - inbredness
- calibration overrides

Ongoing parser-research tooling is included under:

- [tools/field_mapper/README.md](tools/field_mapper/README.md)

That toolkit supports bulk save ingestion, CSV labeling, and reverse-engineering workflows for unresolved fields like sexuality/gayness.

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

On Windows you can also build a standalone executable with `build.bat`.

## Usage

By default the app looks for saves under:

```text
%APPDATA%\Glaiel Games\Mewgenics\<SteamID>\saves\
```

Useful controls:

- `File -> Open Save File...`
- `F5` reload
- `Settings -> Show Family Tree & Inbreeding`
- `Settings -> Locations...`
- `Ctrl+=`, `Ctrl+-`, `Ctrl+0` for zoom

## Inbreeding / Risk Calculation

`Risk%` is based on Wright's Coefficient of Inbreeding using parsed ancestor paths.

High level:

1. Build ancestor paths for each cat
2. Find shared ancestors
3. Reject invalid path combinations that reuse the same cat improperly
4. Sum valid path contributions
5. Normalize to a capped percentage for display

This is useful, but still experimental for very complex pedigrees.

## Known Limits

- Some parser-derived fields are still under active research
- Sexuality / gayness is not fully mapped yet
- Ability / mutation text quality depends on available game data
- Inbreeding and family analysis are good enough to use, but should still be treated as save-research features rather than absolute ground truth

## Credits

- Save parsing research based on [pzx521521/mewgenics-save-editor](https://github.com/pzx521521/mewgenics-save-editor)
- Additional community save-format research and issue reports from players and mod users
