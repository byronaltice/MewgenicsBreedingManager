# Direction #1 — Slot-Aware 0xFFFFFFFE in a Parallel Structure

Investigation plan for finding where the game stores the "part is completely
missing" flag for three defects that the current parser cannot detect:

- **Whommie**: Eye Birth Defect (Blind)
- **Whommie**: Eyebrow Birth Defect (-2 CHA)
- **Bud**: Ear Birth Defect (-2 DEX)

## Hypothesis

For these defects, the game stores the cosmetic base-shape ID in `T[slot+0]`
(eye=139, eyebrow=23, ear=132) so the sprite still renders correctly. The
"part is missing" flag (`0xFFFFFFFE` / GON block `-2`) must therefore live
in a **parallel structure** indexed the same way as `T`.

Candidates:

1. **64-byte pre-T skip block** — top candidate. The parser currently skips
   these 64 bytes without reading them. They sit exactly where a per-slot
   parallel structure would.
2. **Additional per-slot fields elsewhere in the blob** — e.g. a 15-element
   parallel array after the abilities/passives/disorders sections, or
   embedded in the blob tail.

The value we're hunting for is the u32 sentinel `0xFFFFFFFE` (appears as
`FE FF FF FF` in little-endian hex dumps).

## What's already ruled out

- `T[index+1]` (now labeled `*_variant` in the upstream fork) — confirmed
  to be the fur/texture ID echoed across every slot (Whommie=706,
  Bud=161, Kami=174). Not a defect carrier.
- `T[index+2]`, `T[index+3]`, `T[index+4]` — constant 0 or small values
  with no per-slot defect variation.
- The upstream `main-original` repo's new code — also does not detect
  these three defects; their new variant fields are for sprite rendering.

## Cats to use

| Name      | Role in test         | Expected signal                       |
|-----------|----------------------|---------------------------------------|
| Whommie   | Positive (2 defects) | `0xFFFFFFFE` at eye + eyebrow offsets |
| Bud       | Positive (1 defect)  | `0xFFFFFFFE` at ear offset            |
| Kami      | Negative baseline    | No `0xFFFFFFFE` at eye/eyebrow/ear    |
| Petronij  | Whommie's parent     | Pattern to compare inheritance        |
| Romanoba  | Clean control        | No defects anywhere                   |

Slot ordering from `_VISUAL_MUTATION_FIELDS` (15 slots, T indices):

```
 0: fur        3: body       8: head       13: tail
18: leg_L     23: leg_R     28: arm_L      33: arm_R
38: eye_L     43: eye_R     48: eyebrow_L  53: eyebrow_R
58: ear_L     63: ear_R     68: mouth
```

(Note: `_VISUAL_MUTATION_FIELDS` in current `main` starts at index 3 for fur
and uses step 5; double-check against `src/save_parser.py` before writing
any offset math.)

## Phase 1 — Capture the pre-T block

**Goal**: Get the raw 64 bytes immediately preceding the T array for each
test cat.

**Method**:

1. Write a one-off script that mirrors the parser's blob-decompression and
   header-reading up to the skip point. Reuse `BinaryReader` from
   `save_parser.py`.
2. Right before the parser calls `r.read(64)` to skip, capture those 64
   bytes and return them alongside the parsed `Cat`.
3. Print hex dumps (16 bytes per row, with byte offsets) for Whommie, Bud,
   Kami, Petronij, Romanoba. Save output to a `.txt` file for reference.

**Deliverable**: Side-by-side hex dumps of pre-T blocks for the 5 cats.

## Phase 2 — Structural analysis of the pre-T block

**Goal**: Decide how the 64 bytes are structured before searching.

Possible layouts:

| Interpretation          | Size accounting                                |
|-------------------------|------------------------------------------------|
| 16 × u32                | 64 bytes — one slot per u32, 15 slots + 1 pad  |
| 8 × u64                 | 64 bytes — 2 slots packed per u64              |
| 32 × u16                | 64 bytes — maybe variant + flag per slot       |
| Bitmap + other fields   | 2–4 byte bitmap + header/unrelated data        |
| Mixed header + array    | Some bytes are per-cat metadata, rest is array |

**Method**:

1. For each cat, print the block as u32s, u64s, and u16s.
2. Look for:
   - Runs of zeros (padding or unused slots)
   - Obvious sentinels (`0xFFFFFFFE`, `0xFFFFFFFF`)
   - Values matching known per-cat metadata (creation day, fur ID, etc.)
3. Cross-reference byte-varying positions between the 5 cats — invariant
   bytes are format headers/magic, varying bytes carry per-cat data.

**Deliverable**: A short written interpretation of the 64-byte block's
layout, with a diff matrix of which bytes vary across the 5 cats.

## Phase 3 — 0xFFFFFFFE scan in the pre-T block

**Goal**: Directly test the hypothesis.

**Method**:

1. For each of the 5 cats, scan the 64-byte block for the 4-byte sequence
   `FE FF FF FF` at every byte alignment (0, 1, 2, 3 offset).
2. Tabulate results:
   - Whommie should show matches at positions corresponding to eye + eyebrow.
   - Bud should show exactly one match, corresponding to ear.
   - Kami, Romanoba should show zero matches.
3. If matches are found, compute the byte offset and check whether the
   positions are consistent with a 15-slot parallel array indexed the same
   way as T.

**Deliverable**: Scan results table with verdict:
- **HIT** → proceed to Phase 5.
- **MISS** → proceed to Phase 4 (expand search).

## Phase 4 — Fallback: whole-blob 0xFFFFFFFE scan

Run only if Phase 3 comes back empty.

**Goal**: Determine whether the sentinel lives somewhere else in the blob
entirely, not in the pre-T block.

**Method**:

1. For Whommie, Bud, Kami, scan the **entire** decompressed blob for
   `FE FF FF FF` occurrences at all byte alignments.
2. Exclude offsets that fall inside the T array itself (those are the
   known generic detections already handled by the parser).
3. Compute:
   - `whommie_hits - kami_hits` = offsets where Whommie has the sentinel
     but Kami does not → candidate defect flags.
   - `bud_hits - romanoba_hits` = same for Bud's ear defect.
4. Compare the two delta sets. If the positions cluster in one contiguous
   region, that region is the parallel structure.

**Deliverable**: List of candidate offsets. Go back to Phase 2 with those
offsets as the new structure to characterize.

## Phase 5 — Slot-to-offset mapping verification

**Goal**: Confirm the candidate offsets map to the right slots.

**Method**:

1. Given candidate offsets in a parallel structure, assign each to a slot
   key using a consistent rule (e.g. byte offset ÷ 4 = T-slot index ÷ 5).
2. Verify predictions against ground truth:
   - Whommie's hits must map to `eye_L` (or `eye_R`) and `eyebrow_L` (or
     `eyebrow_R`), not any other slot.
   - Bud's hit must map to `ear_L` or `ear_R`.
3. If the mapping is inconsistent (e.g. Whommie's "eye" hit maps to
   `mouth`), the structure is not a simple parallel array — reconsider.

**Deliverable**: A validated `{slot_key: offset}` dictionary ready to be
consumed by the parser.

## Phase 6 — Parser integration

**Goal**: Wire the finding into `save_parser.py` so defects render in-app.

**Method**:

1. In `Cat.__init__`, after reading T, also read the parallel structure
   using the validated offset map.
2. In `_read_visual_mutation_entries`, add a second pass: if the parallel
   structure holds `0xFFFFFFFE` for a slot, treat that slot as having a
   missing-part defect (override the primary `T[index+0]` display).
3. Use the existing GPAK `-2` block lookup path (already in the parser)
   for the display name and stat description.
4. Regression test: Kami, Romanoba, and other no-defect cats must still
   show no defects.

**Deliverable**: A parser change that correctly detects and labels
Whommie's Blind + -2 CHA + Bud's -2 DEX defects.

## Phase 7 — CLAUDE.md update

Replace Direction #1's `**Answer:** _TBD_` with:

- The structure's location (offset + size).
- How to read it (u32 array vs. bitmap vs. other).
- The slot → offset mapping.
- A link back to the parser code that consumes it.

Keep Directions #2 and #3 in place — they remain useful fallbacks if this
direction dead-ends.

## Stop conditions

- **Success**: Phase 5 produces a mapping that correctly flags the three
  known defects with no false positives across the full roster.
- **Dead end**: Phase 4 produces no consistent delta set, OR Phase 5
  shows the candidate offsets don't map coherently to slots. At that
  point, pivot to Direction #2 (bitmap hunt in blob tail) or Direction #3
  (parent blob diff).

## Out of scope

- Any change to the rendering pipeline — visual sprites already render
  correctly for these cats; only defect **detection** is broken.
- Fixing detection for mutations outside the three target defects.
- Pulling upstream `main-original` changes (tracked separately; this
  investigation stays on the existing `main` parser code).
