# Mewgenics Breeding Manager

Your breeding lab for [Mewgenics](https://store.steampowered.com/app/686060/Mewgenics/).

Current release: `v4.0.0`

Track your cats, compare pairings, plan perfect lines, and keep your best breeders organized without doing the math by hand.

## Why Use It

- See your whole roster in one live, sortable table
- Compare breeding pairs with expected offspring stats and inheritance odds
- Plan safe pairings with real inbreeding risk calculations
- Build long-term perfect-stat lines with the `Perfect 7` planner
- Keep lovers, haters, room assignments, and lineage in view
- Read ability and mutation descriptions directly from the game data when available

## What’s New

- Refactored parser, scorer, and optimizer logic out of the main UI file
- Shared breeding engine now powers safe breeding, partners, planning, and optimization
- Perfect 7 planning now respects sexuality, including gay and bi-compatible cats
- Eternal Youth cats are excluded from the donation pool
- Linux/Proton save and game-data support
- Versioned release builds driven by the shared [`VERSION`](VERSION) file

---

<p align="center">
<a href="#main-roster">Main Roster</a> |
<a href="#single-cat-view">Single Cat View</a> |
<a href="#breeding-comparison-view">Breeding Comparison</a> |
<a href="#room-optimizer">Room Optimizer</a> |
<a href="#perfect-7-planner">Perfect 7 Planner</a> |
<a href="#mutation--disorder-planner">Mutation & Disorder Planner</a> |
<a href="#safe-breeding">Safe Breeding</a> |
<a href="#breeding-partners">Breeding Partners</a> |
<a href="#family-tree">Family Tree</a> |
<a href="#exceptional-cats">Exceptional Cats</a> |
<a href="#donation-candidates">Donation Candidates</a> |
<a href="#calibration">Calibration</a>
</p>

---

## Main Roster

![Home Screen](Sceenshots/Home%20Screen.png)

Your command center.

- Search and sort your entire roster
- Mark breeding blacklist and must-breed cats with one click
- See inbreeding risk at a glance
- Spot exceptional breeders and donation candidates instantly

Current thresholds:
- Exceptional breeder: base stat sum `>= 40`
- Donation candidate: low total power, weak top stat, or high aggression
- Must-breed, exceptional, and Eternal Youth cats are excluded from donation marking

## Single Cat View

![Single Cat View](Sceenshots/Single%20Cat%20View.png)

Everything you need on one screen.

- Stats
- Abilities and passives
- Mutations
- Equipment
- Lovers, haters, parents, and grandparents
- Breeding controls

## Breeding Comparison View

![Breeding Comparison View](Sceenshots/Breeding%20Cats%20View.png)

Compare two cats and see what the pairing can produce.

- Offspring stat ranges
- Expected values
- Trait inheritance odds
- Stimulation-adjusted weighting
- Breakpoint hints for pushing stats to 7
- Visual and body-part preview

## Room Optimizer

![Room Optimizer](Sceenshots/Room%20Optimizer.png)

Put the right cats in the right place.

- Optimize room placement
- Respect lovers and haters
- Keep family separation available when you want it
- Minimize variance or prefer stronger pair quality
- Tune for aggression or libido if that matters to your setup

## Perfect 7 Planner

![Perfect 7 Planner](Sceenshots/Perfect%207%20Planner.png)

Plan the long game.

This view helps you build perfect cats across generations instead of just picking the next good pairing.

- Start with the best foundation pairs
- Separate children cleanly
- Rotate and outcross when needed
- Finish with a stable maintenance plan
- Track planned pairs and their offspring outcomes in a dedicated tab

The planner now:
- respects sexuality compatibility
- allows gay same-sex pairings when they are valid
- allows bi-compatible cats to pair broadly
- blocks straight same-sex pairs

## Mutation & Disorder Planner

![Mutation & Disorder Breeding Planner](Sceenshots/Mutation%20and%20Disorder%20Breeding%20Planner.png)

Target a specific trait and work backward from there.

- Find every carrier of a mutation, passive, disorder, or ability
- Compare carrier pairs
- Review inheritance odds
- Track inbreeding risk alongside trait odds
- Filter by room and stimulation

## Safe Breeding

![Safe Breeding](Sceenshots/Safe%20Breeding.png)

Get the safest partner suggestions for a selected cat.

- Inbreeding risk
- Shared ancestors
- Clear risk labels

## Breeding Partners

![Breeding Partners](Sceenshots/Breeding%20Partners.png)

See bonded pairs and keep them together.

Useful for:
- finding mutual lovers
- spotting room mismatches
- planning around favorite pairings

## Family Tree

![Family Tree View](Sceenshots/Family%20Tree%20View.png)

Explore lineage at a glance.

- Parents
- Grandparents
- Children
- Grandchildren

## Exceptional Cats

![Exceptional Cats](Sceenshots/Exceptional%20Cats.png)

Quick filter for your strongest breeders.

## Donation Candidates

![Donation Candidates](Sceenshots/Donation%20Candidates.png)

Quick filter for cats that are likely safe to donate or retire.

Eternal Youth cats are excluded.

## Calibration

![Calibration](Sceenshots/Calibration.png)

For parser tuning and save overrides.

- Override gender, age, aggression, libido, inbredness, and base stats
- Aggression and libido are binned as low `< 30%`, average `30-70%`, high `> 70%`
- Inbredness now includes an `extremely` tier above `80%`
- Save and reload calibration data
- Export and import calibration JSON

## Built For

- Players who want better breeding decisions
- Players chasing perfect stat lines
- Players managing large rosters
- Players who want a clearer view of risk, lineage, and partner quality

## Architecture

The app is split into focused layers:
- `src/save_parser.py` for save parsing and cat data
- `src/breeding.py` for shared compatibility and scoring
- `src/room_optimizer/` for room placement and optimization
- `src/mewgenics_manager.py` for the UI and orchestration

## Requirements

- Python 3.14
- [PySide6](https://pypi.org/project/PySide6/)
- [lz4](https://pypi.org/project/lz4/)

## Install

```bash
git clone https://github.com/frankieg33/MewgenicsBreedingManager
cd MewgenicsBreedingManager
pip install -r requirements.txt
python src/mewgenics_manager.py
```

On Windows, you can also build a standalone executable with `build.bat`.
On Linux, use `build.sh`.

## Versioning

Release builds use the shared [`VERSION`](VERSION) file.

For `v4.0.0`, the packaged archive is named:

```text
MewgenicsManager-4.0.0-windows.zip
MewgenicsManager-4.0.0-linux.zip
```

GitHub Actions also publishes these as release assets automatically for `v*` tags.

## Usage

By default the app looks for saves under:

```text
%APPDATA%\Glaiel Games\Mewgenics\<SteamID>\saves\
```

It also supports common Linux/Proton save layouts and Steam install paths.

Handy controls:
- `File -> Open Save File...`
- `F5` reload
- `Settings -> Show Family Tree & Inbreeding`
- `Settings -> Locations...`
- `Ctrl+=`, `Ctrl+-`, `Ctrl+0` zoom

## Inbreeding Risk

The app uses Wright’s Coefficient of Inbreeding instead of trusting the stored inbredness value.

In short:
1. it walks the family tree
2. it computes kinship recursively
3. it converts COI into birth-defect risk

Risk labels:
- not inbred: `<= 0.10`
- slightly: `<= 0.25`
- moderately: `<= 0.50`
- highly: `<= 0.80`
- extremely: `> 0.80`

## Notes

- Some parser fields are still under active research
- Ability and mutation text quality depends on available game data
- Future game updates may change labels or path handling

## Credits

- Save parsing research based on [pzx521521/mewgenics-save-editor](https://github.com/pzx521521/mewgenics-save-editor)
- Community reports and reverse-engineering help from players and mod users
