# Mewgenics Breeding Manager

A fork of the original repo. Currently it is simply to support the Breed Priority and Party Builder submodules. It will later be refactored to separate into its own thing.

## Doctrine

See CLAUDE.md as the entry point for repository doctrine. Excepting subagents, CLAUDE.md is REQUIRED to be reviewed by agents at the beginning of a new session.

## Core Features

Core features below are for the original repo, left here for reference.

- Load your save file and keep your full roster, lineage, and relationships in one place
- Compare pairings with inheritance odds, expected offspring stats, and risk
- Optimize room layouts with movement-aware scoring
- Plan long-term perfect-stat lines with the Perfect 7 planner
- Read ability and mutation text from `resources.gpak` when available

## Install

This project uses `pip` and `requirements.txt`.

```bash
git clone https://github.com/frankieg33/MewgenicsBreedingManager
cd MewgenicsBreedingManager
pip install -r requirements.txt
python src/mewgenics_manager.py
```

The app will automatically look for `resources.gpak` in common Steam install paths or in the current working directory.

## Build

```bash
build.bat
```

On Linux, use `build.sh`.

## Requirements

- Python 3.14
- PySide6
- lz4
- openpyxl

## Lessons Learned

If you plan to make your own save parser, please see [MISSING_BIRTH_DEFECTS_REPORT.md](./birth-defects-audit/MISSING_BIRTH_DEFECTS_REPORT.md). It details a fix that is not straightforward, and you'll need it if you plan to parse cat defects.

## Credits

- Save parsing research based on [pzx521521/mewgenics-save-editor](https://github.com/pzx521521/mewgenics-save-editor)
- Community reverse-engineering help from players and mod users
- Original idea and reference from frankieg33

