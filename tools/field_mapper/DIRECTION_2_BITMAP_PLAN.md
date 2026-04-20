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

---

## Execution Log

### Phase 1 — 115-byte blob tail dump
**Status: COMPLETE. No defect signal.**

Extracted and hex-dumped the full 115-byte tail for all 5 test cats. Tail
as u32 array: positions +4 (f64, varies per cat), +12 (creation_day u32),
+20 to +27 (`ff ff ff ff ff ff ff ff` constant). Tail u32[5..27] = all
zeros for all cats. No defect-correlated variation found.

### Phase 2 — Byte-level diff and invariant map
**Status: COMPLETE. No defect signal.**

Built a 115-element diff table across all 5 cats. Varying bytes:
- Bytes 4–11: f64 (cat-specific weight/probability)
- Bytes 12–15: creation_day u32
- All other bytes: constant across all cats (mostly zero with constant
  padding at +20..+27)

No byte position correlated with defect presence.

### Phase 3 — Bitmap interpretation test
**Status: COMPLETE. No match.**

Scanned every u16-aligned position in the tail for a bitmap matching
Whommie's eye+eyebrow bits and Bud's ear bits (both normal and inverted
polarity). No matches found at any position.

### Phase 4 — Per-slot byte-array test
**Status: COMPLETE. No match.**

Tested every 15-byte, 30-byte (u16 stride), and 60-byte (u32 stride)
window in the tail. No window matched the expected per-slot defect pattern
for both Whommie and Bud simultaneously.

### Phase 5 — Expanded scan beyond the tail (middle region)
**Status: COMPLETE. No match.**

Scanned the unmapped middle region between t_end and the DefaultMove
marker (~144–400 bytes depending on cat). This region was found to contain
duplicate gender/stat data that the parser does not read. The 3 u32 values
at +4/+8/+12 in this gap vary between cats but do not correlate with defect
presence. Bitmap scan and per-slot window scan over the full middle region:
no hits.

**Side finding — pre-T f64[2] NaN**: `f64[2]` in the 64-byte pre-T block
is `NaN (0xFFFFFFFFFFFFFFFF)` for both Whommie and Bud. However, the same
NaN value also appears for 510/888 cats total (57% of the roster, including
many cats with no defects). Ruled out as a defect-exclusive signal.

**T array definitive check**: For eye_L/R (T[38]/T[43]),
eyebrow_L/R (T[48]/T[53]), ear_L/R (T[58]/T[63]):
- `T[+0]` (mutation_id) is identical between defective and clean cats for
  the affected slots (eye=139, eyebrow=23, ear=132 for Whommie; ear=132
  for Bud vs Kami ear=30 — cosmetic shape variation, not a defect flag).
- `T[+1]` differs only by fur echo (texture ID repeated across all slots).
- `T[+2..+4]` = 0 for all cats in all affected slots.
- Raw byte diff confirmed: ONLY fur echo (T[+1]) and cosmetic base shape
  differ between defective and clean cats in the T eye/eyebrow/ear range.
  No defect-specific data exists in the T array for these three defects.

### Phase 6 — Cross-table SQLite check
**Status: COMPLETE (extended). No confirmed defect signal found.**

Tables checked:
- `properties`: global game state only (no per-cat rows)
- `winning_teams`: empty
- `furniture`: furniture items only
- `files` table (11 rows): enumerated all keys

The `files` table contains a `pedigree` blob (121,168 bytes raw,
NOT LZ4-compressed). This was investigated as a new sub-lead.

**Pedigree blob investigation findings:**

The pedigree blob is indexed by **db_key** (small integer, not cat UID).
Target cat db_keys: Whommie=853, Bud=887, Kami=840, Petronij=841,
Romanoba=826.

Record structure is variable-length. Two observed variants:
- Short: `[cat_id u64, parent_a u64, parent_b u64, f64, slot_data×16 u32]`
  (32-byte prefix, 64-byte slot data = 96 bytes total — seen in Bud,
  Kami, clean cats)
- Long: `[cat_id u64, parent_a u64, parent_b u64, f64, u64(162), NaN f64,
  NaN f64, u64(0), slot_data×16 u32]` (64-byte prefix, 64-byte slot data
  = 128 bytes total — seen in Whommie's primary record at offset 6376)

**NaN hypothesis (Whommie's long record)**: Whommie's primary record at
offset 6376 has NaN f64 values at +40 and +48. Bud's primary record at
offset 3240 has NO NaN values and uses the short variant. The NaN-at-+40/+48
pattern does not appear in any Bud record. **Ruled out** as a universal
defect signal across both cats.

**Slot data comparison** (16 u32s per cat, interpreted as per-slot mutation
values):
- Whommie (slot data at +64): eye_L=538, eye_R=537, eyebrow_L=535,
  eyebrow_R=537, ear_L=538, ear_R=531
- Kami (slot data at +32): eye_L=149, eye_R=0, eyebrow_L=116, eyebrow_R=0,
  ear_L=119, ear_R=0
- Bud (slot data at +32): eye_L=196, eye_R=0, eyebrow_L=168, eyebrow_R=0,
  ear_L=182, ear_R=0

**Bilateral presence observation**: For clean cats (Kami, Petronij, Romanoba),
only the L-side slots have non-zero values; R-side slots = 0. For Whommie
(defective eyes + eyebrows), both L and R eye/eyebrow slots are non-zero.
However, Bud's ear_R slot = 0 despite the ear defect — this pattern does
NOT hold for Bud. **Bilateral presence hypothesis not validated** — it
cannot be a universal defect signal if Bud's ear_R is 0.

**Pedigree investigation verdict**: Extended well beyond Phase 6 scope.
No confirmed defect signal found. The pedigree blob encodes mutation history
data, but does not provide a clean, consistent defect flag distinguishable
from non-defective cat data for all three target defects.

**`npc_progress` file** (22KB in `files` table): Not yet investigated.
Possible remaining sub-lead within Phase 6.

### Stop Condition Assessment

Phase 6 is effectively exhausted (primary leads checked, no candidate found).
The plan's dead-end stop condition applies:

> **Dead end**: Phases 3-6 all come back empty. Pivot to **Direction #3**
> (parent-blob diff — compare Whommie's blob byte-by-byte against Petronij
> and Kami to find which bytes flip when a defect is inherited).

**Current status: Pivoting to Direction #3 pending operator confirmation.**

---

## Remaining Phases (pending)

### Phase 7 — Full-roster validation
Blocked on finding a candidate. No candidate exists yet to validate.

### Phase 8 — Parser integration
Blocked on Phase 7.

### Phase 9 — CLAUDE.md update
Blocked on Phase 8.

---

## Key reference

Direction #1 investigation script and results:
- `tools/field_mapper/investigate_pre_t_block.py`
- `tools/field_mapper/pre_t_block_results.txt`

Direction #2 scripts and results:
- `tools/field_mapper/investigate_blob_tail.py` — Phases 1–6 scan
- `tools/field_mapper/blob_tail_results.txt` — full output (large)
- `tools/field_mapper/investigate_pedigree.py` — pedigree blob search
- `tools/field_mapper/pedigree_results.txt` — pedigree search output
