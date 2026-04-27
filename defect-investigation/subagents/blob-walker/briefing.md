# Blob-Walker Subagent Briefing

You write and run Python investigation scripts against Mewgenics save files. Scoped Bash + Write role.

## Canonical references

- `defect-investigation/findings/blob_corridor_map.md` — byte-for-byte map of the per-cat save blob.
- `defect-investigation/findings/parser_and_gon_reference.md` — T array structure, defect detection logic, GON format.
- `defect-investigation/scripts/common.py` — shared helpers. Reuse; do not duplicate.

## Key helpers in `common.py`

- `BinaryReader(data, pos=0)` — stateful binary reader. Methods: `u32`, `i32`, `u64`, `f64`, `str` (utf-8 length-prefixed), `utf16str`, `skip(n)`, `seek(n)`, `remaining()`.
- `decompress_cat_blob(blob) -> bytes` — LZ4-decompresses the SQLite-stored cat blob.
- `iter_cats_from_save(path)` — yields `(db_key, blob)` tuples.
- `parse_cat_known_fields(raw)` — parses stable anchors (breed, uid, name, parents, stats). Use this rather than re-implementing header parsing.
- `get_alive_key_sets(path) -> (house_keys, adventure_keys)` — for filtering live cats.

## Reference cats (memorize these)

```python
FOCUS = {
    "Whommie":  853,  # defect+ (Blind, -2 CHA)
    "Bud":      887,  # defect+ (-2 DEX)
    "Kami":     840,  # control
    "Petronij": 841,  # control
    "Murisha":  852,  # control
}
DEFECT_POSITIVE = {853, 887}
CLEAN_CONTROLS  = {840, 841, 852}
```

## Script conventions (extracted from `investigate_direction41.py`)

```python
from __future__ import annotations
import os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if not (ROOT / "test-saves").exists():
    ROOT = ROOT.parents[2]
sys.path.insert(0, str(ROOT / "src"))

from save_parser import STAT_NAMES, parse_save  # noqa: E402

DEFAULT_SAVE = ROOT / "test-saves" / "investigation" / "steamcampaign01_20260424_191107.sav"
SAVE = Path(os.environ.get("INVESTIGATION_SAVE", str(DEFAULT_SAVE)))
```

## Output path convention (NEW — enforced)

Write results **directly** to:

    defect-investigation/audit/direction/directionNN_results.txt

Do not write next to the script. Do not write under `scripts/`. Inside the script:

```python
OUT = ROOT / "defect-investigation" / "audit" / "direction" / f"direction{NN}_results.txt"
```

Adjust the `ROOT` path math if needed so this resolves correctly from `scripts/investigate-direction/`.

## Save file scope

- Only read save files under `test-saves/`.
- Never read save files outside the repo (no `%LOCALAPPDATA%`, no user save directories).
- Operator's CLAUDE.md forbids reading or modifying JSON sidecars outside `test-saves/` — STOP and inform the operator if a task requires it.

## What NOT to do

- Do not import from `breed_priority/` or any Qt module.
- Do not modify `scripts/common.py` without explicit instruction in the task prompt.
- Do not touch `findings/`, `archive/`, or `game-files/`.
- Do not write outside `defect-investigation/scripts/investigate-direction/` and `defect-investigation/audit/direction/`.
- Do not run pytest (CLAUDE.md: there are no tests).
