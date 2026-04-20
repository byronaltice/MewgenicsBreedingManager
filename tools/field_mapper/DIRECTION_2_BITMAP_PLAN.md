# Direction #2 — Missing-Parts Bitmap / Non-Sentinel Flag Hunt

Investigation plan for Direction #2 of the birth-defect mystery. Picks up
from Direction #1, which ruled out `0xFFFFFFFE` as the defect carrier —
the sentinel does not appear anywhere in the cat blobs for the three
affected defects.

## What we're hunting for

For each of the three undetected defects, the game must store **some**
per-slot flag — just not as the `0xFFFFFFFE` sentinel. Candidates:

- A 15-bit (or 16-bit) **bitmap** where each bit = "slot N is a missing
  part". Two bytes would cover all 15 body slots.
- A **per-slot byte array** (15 u8 values) with a non-zero flag per
  affected slot.
- A **per-slot u16 array** (30 bytes) — e.g. slot index ↔ defect code.
- A **packed structure** using some other value than `0xFFFFFFFE` —
  e.g. slot_id = 0, or slot_id = a specific "defect" ID we haven't
  catalogued.
- A **per-defect record list** elsewhere in the blob or another SQLite
  table, keyed by slot name or index.

## What we know

Blob section map (Whommie, 938 bytes total):

| Section             | Status                         |
|---------------------|--------------------------------|
| Header              | parsed                         |
| breed_id, uid, name | parsed                         |
| name_tag, parents   | parsed                         |
| collar + u32        | parsed                         |
| **Pre-T 64 bytes**  | confirmed 8 f64 seeds (Dir #1) |
| T[72] array         | parsed (288 bytes)             |
| Abilities           | parsed                         |
| Passives (3 slots)  | parsed                         |
| Disorders           | parsed                         |
| Gender, stats, etc. | parsed                         |
| Class string        | parsed (near end)              |
| **Blob tail (115 bytes after class string)** | partially mapped — primary Dir #2 target |

Known tail sub-fields (from earlier notes):

- `+4`: varying f64 (role unknown — possibly a probability/weight)
- `+12`: `creation_day` u32
- `+20`: `ff ff ff ff ff ff ff ff` — 8 constant bytes across all cats
- Remaining ~87 bytes: unmapped

## Expected signals per cat

| Cat       | Defect slots (per game)           | Expected flags        |
|-----------|-----------------------------------|-----------------------|
| Whommie   | eye (Blind) + eyebrow (-2 CHA)    | 2 hits                |
| Bud       | ear (-2 DEX)                      | 1 hit                 |
| Kami      | (none)                            | 0 hits                |
| Petronij  | (none)                            | 0 hits                |
| Romanoba  | (none)                            | 0 hits                |

Slot bit positions assuming a 15-slot bitmap indexed by
`_VISUAL_MUTATION_FIELDS` order (slot 0 = fur, slot 14 = mouth):

```
 slot | body part
------+----------
   0  | fur
   1  | body
   2  | head
   3  | tail
   4  | leg_L
   5  | leg_R
   6  | arm_L
   7  | arm_R
   8  | eye_L
   9  | eye_R
  10  | eyebrow_L
  11  | eyebrow_R
  12  | ear_L
  13  | ear_R
  14  | mouth
```

If the game encodes each defect on one side (L) or both (L+R), Whommie's
bitmap would show bits 8/9 and 10/11, Bud's bitmap would show bits 12/13.

## Phase 1 — Extract and dump the 115-byte blob tail

**Goal**: Get the full raw tail bytes for all 5 test cats.

**Method**:

1. Locate the end of the class string in each blob (class string ends
   at `len(blob) - 115` per `_CLASS_STRING_TAIL_OFFSET`).
2. Extract bytes `[end_of_class_string : len(blob)]` — should be exactly
   115 bytes.
3. Dump each as hex (16 bytes per row with offsets).
4. Also interpret as:
   - u32 array (28 full u32s + 3 trailing bytes)
   - u64 array (14 u64s + 3 trailing bytes)
   - u16 array (57 u16s + 1 trailing byte)
   - 115 individual u8s

**Deliverable**: Hex + multi-format dumps side-by-side for all 5 cats.

## Phase 2 — Byte-level diff and invariant map

**Goal**: Identify which byte positions vary vs. which are constant.

**Method**:

1. Build a 115-element table showing each cat's byte value at each
   offset.
2. Classify each offset:
   - **Constant** across all 5 cats → format padding, not interesting
   - **Varies only with creation_day / f64** → already known fields
   - **Varies in a way correlated with defect presence** → prime suspect

3. Focus attention on offsets where Whommie and Bud differ from Kami /
   Petronij / Romanoba, but Whommie and Bud don't necessarily match
   each other (since they have different defects).

**Deliverable**: A varying-bytes table, with likely known-field ranges
annotated and defect-correlated ranges flagged.

## Phase 3 — Bitmap interpretation test

**Goal**: Test the "2 byte bitmap of missing parts" hypothesis directly.

**Method**:

1. For each u16 position in the blob tail, for each cat, extract the 16
   bits.
2. Define the expected bitmap per cat:
   - Whommie: bits covering eye + eyebrow slots
   - Bud: bits covering ear slots
   - Kami, Petronij, Romanoba: all zero
3. Scan every u16-aligned position for a match where:
   - Whommie has bits set in the eye/eyebrow range
   - Bud has bits set in the ear range only
   - Kami / Petronij / Romanoba have 0
4. Also try the reverse: "0 means defect, 1 means present" (in case the
   flag polarity is inverted).

**Deliverable**: A list of candidate u16 offsets (if any) whose values
match the defect pattern.

## Phase 4 — Per-slot byte-array test

**Goal**: If no bitmap match, test the "15 bytes per cat" layout.

**Method**:

1. For each 15-byte window in the tail (positions 0..100), treat it as
   a per-slot array indexed by slot number.
2. Check whether:
   - Whommie's window has non-zero bytes at slots 8, 9, 10, 11 (eye +
     eyebrow) and zero elsewhere.
   - Bud's window has non-zero bytes at slots 12, 13 only.
   - Kami's, Petronij's, Romanoba's windows are all zero.
3. Also try u16 stride (30-byte window = 15 u16s) and u32 stride.

**Deliverable**: Candidate window offset if a match is found.

## Phase 5 — Expand search beyond the tail

**Goal**: If neither bitmap nor per-slot array lives in the tail, scan
the full blob.

**Method**:

1. For each byte offset in the blob (excluding regions the parser
   already consumed — T array, stats, abilities, etc.), test the same
   bitmap/per-slot hypotheses.
2. The parser's `r.pos` trail identifies consumed regions; anything
   untouched is fair game.
3. Particular attention to gaps between parsed sections (e.g. any
   trailing bytes after the disorders list before the gender block).

**Deliverable**: Full blob-offset coverage report with any candidate
offsets highlighted.

## Phase 6 — Cross-table check (SQLite)

**Goal**: Rule out (or confirm) that the flag lives in another SQLite
table entirely, not the cat blob.

**Method**:

1. Enumerate all tables in `steamcampaign01.sav`. From earlier work we
   know: `cats`, `furniture`, `files`, `properties`, `winning_teams`.
2. For each non-`cats` table, check for rows keyed by cat UID with
   fields that could encode defects.
3. Also check whether the `cats` table has any column beyond
   `(key, data)` we've overlooked.

**Deliverable**: A short verdict on whether any other table contains
per-cat defect data. Expected result: no — but worth confirming now to
close the door.

## Phase 7 — Slot→offset mapping verification

**Goal**: If a candidate structure is found in Phases 3-5, verify the
mapping against ground truth.

**Method**:

1. For each candidate offset and encoding, enumerate all cats in the
   save (not just the 5 test cats).
2. For every cat flagged by the candidate, check whether the game
   actually shows that defect. Use any additional known defect cats as
   positive controls, and a large sample of clean cats as negative
   controls.
3. Reject candidates with false positives (flags set on cats with no
   visible defect) or false negatives (no flag on a cat with a visible
   defect).

**Deliverable**: A validated `{slot_index: offset, encoding}` spec
ready to be consumed by the parser.

## Phase 8 — Parser integration

**Goal**: Wire the finding into `src/save_parser.py`.

**Method**:

1. In `Cat.__init__`, after reading the class string, decode the
   missing-part flags from the tail.
2. In `_read_visual_mutation_entries`, add a second pass: if the
   missing-part flag is set for a slot, treat that slot as having a
   `-2` missing-part defect (override the primary `T[index+0]`).
3. Reuse the existing GPAK `-2` block lookup path for the display name
   and stat description.
4. Regression test: Kami, Petronij, Romanoba, and the rest of the
   non-defective roster must continue to show no defects.

**Deliverable**: Parser change that correctly detects Whommie's Blind
and -2 CHA defects and Bud's -2 DEX defect, with no regressions on the
rest of the roster.

## Phase 9 — CLAUDE.md update

Replace Direction #2's `**Answer:** _TBD_` with:

- The structure's blob-relative offset and length.
- The encoding (bitmap / byte array / other).
- The slot-to-offset (or bit) mapping.
- A link back to the parser code that consumes it.

Keep Direction #3 in place — the parent-blob comparison remains a
useful cross-check (and a backup if Direction #2 also dead-ends).

## Stop conditions

- **Success**: Phase 7 validates a candidate across the full roster
  with zero false positives and zero false negatives, and Phase 8
  wires it into the parser cleanly.
- **Dead end**: Phases 3-6 all come back empty. At that point, pivot
  to **Direction #3** (parent-blob diff — compare Whommie's blob
  byte-by-byte against Petronij and Kami to find which bytes flip
  when a defect is inherited).

## Out of scope

- Fixing mutation detection for IDs other than the three target
  defects.
- Any change to the rendering pipeline — sprites already render
  correctly; only defect detection is broken.
- Pulling upstream `main-original` parser changes (tracked separately;
  the investigation stays on current `main`).

## Key reference

Direction #1 investigation script and results:
- `tools/field_mapper/investigate_pre_t_block.py`
- `tools/field_mapper/pre_t_block_results.txt`

The Direction #2 script should be named
`tools/field_mapper/investigate_blob_tail.py` and follow the same
pattern (load the 5 test cats, dump structures, run hypothesis checks,
emit a results file).
