# Investigation Handoff — Birth Defect Flag Location

## What you're doing

Reverse-engineering where the Mewgenics save file stores "completely missing
body part" birth defect flags. Three defects are visible in-game but not
detected by the parser:

- **Whommie**: Eye Birth Defect (Blind) + Eyebrow Birth Defect (-2 CHA)
- **Bud**: Ear Birth Defect (-2 DEX)

Read `CLAUDE.md` in the repo root for full project context. The relevant
section is **"Visual Mutation / Birth Defect Parsing"** — read it entirely.

## Where everything is

| File | Purpose |
|------|---------|
| `tools/field_mapper/DIRECTION_2_BITMAP_PLAN.md` | **Your primary reference.** Full plan + execution log of everything tried so far. Read this first. |
| `tools/field_mapper/investigate_blob_tail.py` | Phases 1–6 scan script |
| `tools/field_mapper/blob_tail_results.txt` | Full output of Phases 1–6 (large) |
| `tools/field_mapper/investigate_pedigree.py` | Pedigree blob search script (**worktree-only**, not in main — see note below) |
| `tools/field_mapper/pedigree_results.txt` | Pedigree search output (**worktree-only**, not in main — see note below) |
| `src/save_parser.py` | The parser you will eventually modify |
| `test-saves/steamcampaign01.sav` | The save file to work with |

> **Note — worktree-only files**: `investigate_pedigree.py` and
> `pedigree_results.txt` were never committed to main. They exist only in
> worktree `gifted-colden-22a33e` at:
> `%USERPROFILE%\gitprojects\MewgenicsBreedingManager\.claude\worktrees\gifted-colden-22a33e\tools\field_mapper\`
> They are useful for reference but not required to proceed with Direction #3.

## Current status

**Direction #2 is exhausted.** Read the Execution Log in
`DIRECTION_2_BITMAP_PLAN.md` for the full story. Short version:
- Blob tail (115 bytes after class string): no defect signal
- Middle region (t_end to DefaultMove, ~144–400 bytes): no defect signal
- Pre-T f64[2] NaN: present on 57% of all cats — not defect-exclusive
- T array: confirmed NO defect data for affected slots
- SQLite cross-table check: pedigree blob investigated extensively, no
  confirmed defect signal found

The plan's dead-end stop condition has been reached.

## Your next step: Direction #3

Direction #3 is a **parent-blob byte diff**. The logic:

Whommie's parents are **Petronij** and **Kami** — both have no defects.
Whommie inherited the defects. If the defect flag is stored in Whommie's
cat blob, comparing Whommie's raw blob byte-by-byte against Petronij's and
Kami's blobs should reveal which byte positions differ due to the defect
(vs. bytes that differ due to unrelated things like name, stats, etc.).

Cross-checking: Bud's defect (ear) must show a flag somewhere in Bud's blob.
You'll need to find Bud's parents too (use `cat._parent_uid_a` /
`cat._parent_uid_b` and match against `all_cats`) and do the same diff.

### Approach

1. Load all cats from the save using `parse_save()`.
2. Identify Whommie, Bud, and their respective parents.
3. Extract the raw (decompressed) blob for each cat. The blob is stored
   LZ4-compressed in the SQLite `cats` table keyed by `cat.db_key`. To
   decompress: read `u32(uncomp_size)` then `lz4.block.decompress(data[4:], uncompressed_size=uncomp_size)`.
4. Byte-diff Whommie's blob vs each parent's blob. Mark each differing
   offset as: (a) known field (use the parser's field map), (b) unknown.
5. Narrow the candidate list to offsets that are ALSO different between
   Bud and Bud's parents in a compatible way (i.e. a position that is
   zero/clean in parents but non-zero/flagged in the defective offspring).
6. If a candidate offset survives both Whommie and Bud diffs, test it
   against the full 888-cat roster (Phase 7 of the plan).

### Useful parser attributes

```python
result = parse_save(SAVE_PATH)
all_cats = result[0]           # list of Cat objects
cat = cat_map['Whommie']
cat._uid_int                   # u64 integer UID
cat.db_key                     # small integer key into SQLite cats table
cat._parent_uid_a              # u64 parent A UID (0 if none)
cat._parent_uid_b              # u64 parent B UID (0 if none)
cat.defects                    # list of detected defect dicts (currently empty for Whommie/Bud)
```

### Raw blob extraction

```python
import sqlite3, lz4.block, struct

conn = sqlite3.connect(SAVE_PATH)
row = conn.execute("SELECT data FROM cats WHERE key=?", (cat.db_key,)).fetchone()
raw = bytes(row[0])
uncomp_size = struct.unpack_from('<I', raw, 0)[0]
blob = lz4.block.decompress(raw[4:], uncompressed_size=uncomp_size)
```

### Known parsed blob regions (to filter from the diff)

These regions vary between cats for reasons unrelated to defects:

| Region | What it is |
|--------|-----------|
| Early bytes | breed_id, uid, name (utf16), name_tag, parent UIDs, collar |
| Pre-T 64 bytes | 8 f64 seeds/probabilities |
| T[72] × 4 bytes = 288 bytes | Visual mutation array (T[+1] varies by fur) |
| Middle region | Abilities, passives, disorders (variable length) |
| Post-DefaultMove | Gender token fields, raw_gender str, f64, stat_base[7], stat_mod[7], stat_sec[7] |
| Blob tail +4..+11 | f64 (cat-specific weight) |
| Blob tail +12..+15 | creation_day u32 |

Bytes that differ between Whommie and parents OUTSIDE these regions are
the prime suspects.

## Script naming convention

Follow the pattern of previous scripts:
- Name it `tools/field_mapper/investigate_direction3.py`
- Write output to `tools/field_mapper/direction3_results.txt`
- Print and write simultaneously (see existing scripts for the `out()` pattern)

## Success condition

Find a byte offset (or small set of offsets) in the cat blob where:
- Defective cats (Whommie, Bud) have a non-zero (or otherwise flagged) value
- Clean cats (parents, controls) have zero (or unflagged) value
- The pattern holds across the full 888-cat roster with zero false positives
  and zero false negatives

Then wire the finding into `src/save_parser.py` (Phase 8 of the plan) and
update `CLAUDE.md`'s "Open investigation directions" section (Phase 9).
