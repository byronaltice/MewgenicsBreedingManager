# Defect Investigation Notes

### Visual Mutation / Birth Defect Parsing

**T array structure** — `Cat.__init__` reads a 72-element u32 array `T` immediately after a 64-byte skip block. Each body-part slot is defined by `_VISUAL_MUTATION_FIELDS` with a fixed `table_index` into T. Known field layout per 5-element slot window (slots at indices 3, 8, 13, 18 ... 68):
- `T[index+0]` = mutation_id (the actual mutation or defect in that slot; 0 / 0xFFFFFFFF = empty)
- `T[index+1]` = always equals `T[0]` (the fur/texture ID repeated in every slot — game engine artifact, not a stat)
- `T[index+2]` = 0 in all observed saves
- `T[index+3]` = small non-zero for some slots (role unknown); does NOT encode mutation stat modifiers
- `T[index+4]` = 0 in all observed saves

The fur slot at index 0 has only 3 fields (`T[0]`, `T[1]`, `T[2]`); `T[1]` = small integer breed/body variant ID (e.g., 8 or 31), `T[2]` = highly variable (0xFFFFFFFF mode) — neither encodes birth defect flags (confirmed via Direction 17).

**Mutation stat modifiers** are NOT stored in T. They are defined in the GPAK GON files and the CSV strings table, and applied by the game to stat_mod at save time. The parser reads mutation stat effects from `_VISUAL_MUT_DATA` (populated from the GPAK) purely for display.

**Defect detection** — `is_defect` is set True when: (a) `700 <= mutation_id <= 706` or `mutation_id == 0xFFFFFFFE` (legacy hardcoded range), OR (b) the GPAK entry for that mutation has `tag birth_defect` in its GON block. The GPAK flag is the authoritative source and catches IDs outside the original range (e.g. Blob Legs = 707, No Ears = ears GON ID 2).

**GPAK GON format for mutations** — Each body-part GON file (e.g. `data/mutations/legs.gon`) contains numbered blocks. Each block may have:
- A `// comment` as the display name
- `tag birth_defect` to mark it as a birth defect
- Inline stat modifiers: `str 1`, `cha -1`, `spd -2`, `speed -4` (alias for spd), etc.
- `desc "MUTATION_CATEGORY_ID_DESC"` pointing to the CSV strings table for text effects
- A `passives { ... }` sub-block listing gameplay passive effects

`_parse_mutation_gon` extracts all of these and returns `{slot_id: (name, combined_stat_desc, is_birth_defect)}`. The combined `stat_desc` always merges GON header stats with the CSV description (e.g. `-1 CHA, 10% dodge chance`). Low-ID blocks (< 300) are parsed only if they have `tag birth_defect`.

**`_VISUAL_MUT_DATA`** — Module-level `dict[str, dict[int, tuple[str, str, bool]]]` keyed by GPAK category (e.g. `'legs'`, `'ears'`, `'texture'`). Populated via `set_visual_mut_data()`. Tuple = `(display_name, stat_desc, is_birth_defect)`.

**Known base-shape T values** — Most ear_L / ear_R slot values for cats without ear mutations are < 300 (e.g. 30, 56, 132) and represent cosmetic base ear shapes, not mutations. These are correctly skipped by the parser. Do not confuse them with defect IDs.

**Unresolved Defects: Current State**

Goal: find how the game applies three confirmed birth-defect effects that the parser does not currently detect:

- Whommie: Eye Birth Defect (Blind)
- Whommie: Eyebrow Birth Defect (-2 CHA)
- Bud: Ear Birth Defect (-2 DEX)

Known facts:

- The affected T slots contain normal base-shape IDs: eye=139, eyebrow=23, ear=132.
- Clean cats can share those same IDs. Kami/Romanoba share Whommie's eye/eyebrow IDs without those defects.
- The expected literal defect ID `0xFFFFFFFE` does not appear anywhere in Whommie/Bud cat blobs outside the T array.
- The GON definitions for the matching effects are block `-2` (`0xFFFFFFFE` as u32): eyes = `blind -1`, eyebrows = `cha -2`, ears = `dex -2`.
- Do not assume the rendered body part is visually absent. The confirmed fact is only that the game applies the defect effect while the T slot stores a normal base-shape ID.
- The parser already detects normal explicit birth-defect IDs, including explicit `0xFFFFFFFE`, when they appear in `T[index+0]`.

Current working model:

The missing effects are probably not stored as a simple literal second T array, obvious bitmask, `2`, or `0xFFFFFFFE` value. Direction 32 found the executable-side lead: `glaiel::CatData::breed` (`FUN_1400a6790`) calls birth-defect helpers and `FUN_1400a5390` uses `0xFFFFFFFE` internally when a body-part record's byte at `CatPart+0x18` is zero.

Direction 33 mapped the direct serializer: `FUN_14022ce10` writes T[0..2] from top-level CatData fields, then 14 body-part records; each record is exactly `CatPart+0x04`, `+0x08`, `+0x0c`, `+0x10`, `+0x14`. The `CatPart+0x18` byte used by `FUN_1400a5390` is not serialized in the T array.

Direction 34 corrected the next assumption: `FUN_1400caa20` is `CatData::MutatePiece(... )::lambda_1`; after it finds a tagged mutation entry it calls `FUN_1400cb130`. `FUN_1400cb130` writes the selected mutation ID into the same per-part visible ID fields that Direction 33 mapped to T. Examples:

- part category `6` writes both eyes at `CatData+0x2dc` and `CatData+0x330` = saved T[38] and T[43].
- part category `7` writes both eyebrows at `CatData+0x384` and `CatData+0x3d8` = saved T[48] and T[53].
- part category `8` writes both ears at `CatData+0x42c` and `CatData+0x480` = saved T[58] and T[63].

Therefore, if the normal `birth_defect`/`MutatePiece` path applied no-eyes/no-eyebrows/no-ears as block `-2`, the save should contain `0xFFFFFFFE` in T, just like Alaya's explicit no-ears defect does. Whommie and Bud do not. Treat `CatPart+0x18` as a useful runtime clue, not a direct explanation for the saved missing defects.

Direction 34 also mapped the display rule in `FUN_1400e38c0`: it calls `FUN_1407b1190` to look up the mutation entry for the part ID, then checks whether the entry tag text equals `"birth_defect"`. If true, it uses `BirthDefectTooltip`. This supports the parser's GPAK tag-based detection for IDs that are actually present in T, but it does not explain Whommie/Bud because their saved IDs are ordinary base-shape IDs.

Direction 34 follow-up: `FUN_1400c17f0` is not a body-part writer. It reads strings from the `"birth_defects"` GON/object value and calls `FUN_1400c1600`. `FUN_1400c1600` checks a small serialized string list at `CatData+0x910..0x9b0`, then `FUN_1400c1ac0` writes the selected string and a u32 tier/flag into that list and applies any linked GON effects such as `grant_ability` or `lock_item_slot`. `FUN_14022d360` serializes this area.

Direction 35 closes this lead. Reading the existing FUN_14022d360 decompile end-to-end, the corridor has exactly four `(string, u32)` slots at `+0x910/+0x930`, `+0x938/+0x958`, `+0x960/+0x980`, `+0x988/+0x9a8`. The parser reads all four: corridor slot 0's string is the 11th item of the "DefaultMove" run (`run_items[10]`, mapped to `passives[0]`), corridor slot 0's u32 is `passive1_tier`, and the three subsequent `(string, u32)` tail slots are corridor slots 1-3. Whommie's exact disk size from `run_start` to `equipment_start` (207 bytes = 0xcf) matches a recomputation of 11 strings + 1 u32 + 3 (string, u32) pairs, leaving no hidden bytes in this corridor. For Whommie and Bud all four slot strings are literal `"None"` with tier `1`. The corridor is therefore not the carrier for the missing Whommie/Bud effects. See `tools/field_mapper/direction35_results.txt` for the full write order.

Direction 36 closes the pre-corridor strings lead. A roster scan of all 947 cats at the 10 fixed-stride slots `+0x7d0..+0x8f0` found zero strings dropped by the parser's `_IDENT_RE` filter (only literal `"None"` / `"DefaultMove"` are intentionally treated as filler). Whommie and Bud have no unique tokens at any slot relative to the full roster. See `tools/field_mapper/direction36_results.txt`.

Directions 37-39 close the post-equipment region. Direction 37 mapped `FUN_14022d360` after the 5th `FUN_14022b1f0` call: class string at `+0xc10`, then small fixed writes (`+0xc30` u32, `+0xc50` f64, `+0xc38` f64 [v>7], `+0xc40` f64 [v>8]), then a variable byte vector via `FUN_1402345e0`, then `+0xc34` u32 [v>0xe], `+0xc00` f64 [v>0xf], three u8 at `+0xc08/+0xc09/+0xc0a` [v>0xf], and finally a 16-u32 array at `+0x744..+0x780` [v>0x11]. Direction 38 decompiled `FUN_1402345e0` and confirmed it is a generic `{u64 size; size * u8}` byte-vector serializer at `CatData+0x8` with no defect semantics (no `birth_defect` strings, no GON lookups). Direction 39 roster-scanned all 947 cats for the byte vector size, the three u8 flags, and the 16-u32 array: Whommie, Bud, Kami, Petronij, Murisha are indistinguishable in every field; the byte vector is empty or trivial (single 0x00) for all 5 reference cats; the three u8s are `(0,0,0)` for Whommie/Bud/Petronij/Murisha and `(3,3,0)` for Kami (counter-shape, correlated with class/passives, not defects); the 16-u32 array is all zero for all 5 reference cats. None of these fields is the carrier. See `tools/field_mapper/direction37_results.txt`, `direction38_results.txt`, `direction39_results.txt`.

**Best Path Forward**

The on-disk per-cat blob is now fully mapped byte-for-byte from header through tail and no field distinguishes Whommie/Bud from clean controls. Directions 33-39 close every saved field including: T body-part records, `+0x910..+0x9b0` effect-list corridor, the 10 `+0x7d0..+0x8f0` ability-run strings, the post-equipment `+0xc00..+0xc40` fixed scalars and three u8 flags, the variable byte vector at `CatData+0x8`, and the 16-u32 array at `+0x744..+0x780`.

Direction 40 ruled out the GON-lookup hypothesis: IDs 139 (eyes), 23 (eyebrows), 132 (ears) have NO GON entries — they are anonymous base cosmetic shapes, not mutations. Parser correctly returns None for them.

Direction 41 ruled out saved stat arrays as the carrier: Whommie/Bud have `stat_mod = [0,0,0,0,0,0,0]` in the save. Class bonuses (e.g. Druid on Kami) ARE baked into stat_mod, but defect penalties are NOT. Defects are applied through a different mechanism than class bonuses — likely runtime/display-time, not save-time.

Direction 42 mapped the runtime DISPLAY chain:
- `FUN_1400c9810` builds the effective-mutations list by reading `CatPart+0x18` (a runtime-only "missing part" flag NOT serialized in the T-array; if 0, effective partID = `0xFFFFFFFE`).
- `FUN_1400e38c0` (tooltip builder) calls `FUN_1407b1190`; with `0xFFFFFFFE` it finds GON block -2 (tag `birth_defect`) and shows `BirthDefectTooltip`. There is NO fallback path — display strictly requires the `0xFFFFFFFE` substitution.

Direction 43 corrected a Direction 42 misidentification and found a new key:
- `FUN_1401d2ff0` is `GlobalProgressionData::ComputeSaveFilePercentage`, NOT the per-cat save loader. The `FUN_1400ca4a0` call at `1401d3c8b` applies progression-milestone mutations (save-completion unlocks), not per-cat defect reconstruction. Direction 42's interpretation that this was the post-deserialize defect applier is WRONG.
- However: `FUN_140230750` (cat save-context loader) reads `"random_seed"` from the SQLite `properties` table and seeds xoshiro256** at `TLS+0x178`. All session-wide `FUN_1400ca4a0` calls use this seeded state.
- `FUN_1400ca4a0` itself does NOT read from any CatData offset directly. It loads `birth_defect`-tagged candidates from `_DAT_141130700`, filters via lambda, shuffles via the seeded RNG, and applies via `FUN_1400caa20` → `FUN_1400cb130` (the part writer).

**Open question after Direction 43:** If defects are deterministic from `random_seed`, the parser cannot derive Whommie/Bud's specific defects without replaying the entire game RNG — implausible. So one of:
(i) Per-cat defect results ARE saved somewhere and `random_seed` is only the RNG source at breed time. Then `CatPart+0x18` must be reconstructed at load time from a per-cat saved signal we haven't found.
(ii) There is a per-cat saved RNG state (creation-event seed) that lets the game replay just that cat's defect roll. Such a field would be small and unmapped in the blob — but the blob is byte-for-byte mapped, so this requires a mis-labeled existing field.
(iii) The defect's gameplay effects (stat_mod, blind status) are applied without the parser-visible `CatPart+0x18 = 0` substitution — meaning the defect display the user sees comes through a different code path entirely than the one Direction 42 traced.

**Confirmed by user (2026-04-25):** Defects are STABLE across save reloads. This eliminates "purely runtime-derived" hypotheses. The defect data is fully on disk per-cat — either as an explicit saved field (in the blob or SQLite) or as a per-cat seed/key from which the defect can be derived. The parser CAN derive these defects given the right input; we just haven't located the input yet.

**User-provided hint (2026-04-25):** The GON files contain the literal string `"Blind."` (with period) — the exact display string for Whommie's Eye Birth Defect, likely the CSV/locale-resolved `desc` for eyes GON block `-2`. This is a **code-tracing aid, not a signal to re-scan the blob**. Treat it as a landmark in the executable: find the function that produces the `"Blind."` display for a cat, then trace BACKWARD to discover what saved input drives it. Do NOT re-scan the blob for this string — extensive blob scanning has already been done and is unlikely to surface a missed carrier.

**Direction 45 — Per-cat load chain mapped end-to-end (2026-04-26):**

Renamed/identified key functions:
- `FUN_14022d360` = `glaiel::SerializeCatData(CatData&, ByteStream&, bool)` — symmetric serializer. `param_2[0]` is ByteStream mode (0=write, 1/2=read). `param_3` is purely a version-strict guard ("cannot load cat saved on older version of game"). NO defect-application logic, NO RNG, NO `FUN_1400ca4a0` calls. Direction 33 was correct: each body-part record writes exactly 5 u32s at +0x04..+0x14.
- `FUN_14022dfb0` = `glaiel::MewSaveFile::Load(__int64, CatData&)` — per-cat roster blob loader. Reads SQLite `cats` table by db_key, deserializes via SerializeCatData, then bone placement.
- `FUN_140230750` = `glaiel::MewSaveFile::Load(__int64, SaveFileCat&)` — single-cat **save_file_cat** (player's protagonist) loader. SQLite key `"save_file_cat"`. NOT the roster loader. Direction 43's earlier confusion is resolved: `random_seed` is read here only when initializing a fresh adventure (`save_file_cat` missing).
- `FUN_1400d5600` = lazy on-demand cat retrieval (`get_cat_by_db_key`). Hash-cache lookup → SQLite check → calls `MewSaveFile::Load`. **There is NO eager roster loader.** All 947 cats are loaded individually on first access through this 200+ caller hub.
- `FUN_1400b5260` = cat default initializer. Uses TLS+0x178 xoshiro256** RNG directly, calls `FUN_140732750` (body-part randomizer), `FUN_140734760` (bone placement). Runs BEFORE deserialize.
- `FUN_140732750` = body-part container randomizer. Loads `data/cat.gen.gon`, queries `num_textures/num_palettes/num_wrinkles/num_grays/num_claws/num_bodies/num_heads/num_tails/num_legs/num_ears/num_eyes/num_brows/num_mouths`, calls `FUN_140943040(0, count, RNG)` to pick a random ID for each. Writes part-category type tags at record starts (record_k+0 = category id like 0x0..0x15). Calls `FUN_140733100(param_1, param_2)` before bone placement — `FUN_140733100` is the remaining unmapped step in the chain.
- `FUN_140734760` = bone/transform placement only ("CatHeadPlacements" GON; copies position/rotation for head/abody/mouth/feet/atail/ahead/aneck/aface anchors). Does NOT write the missing-part flag.

**Body-part container layout (corrected from Direction 33):**
- Container = `CatData+0x60`. Saved records 0..13 at container offsets `+0x2c, +0x80, +0xd4, +0x128, +0x17c, +0x1d0, +0x224, +0x278, +0x2cc, +0x320, +0x374, +0x3c8, +0x41c, +0x470` (stride `0x54`).
- Each saved record k holds 5 u32s at offsets `+0x04..+0x14` written by `FUN_14022cd00`. Bytes `+0x18..+0x53` of each record are **runtime-only** (not in the saved blob).
- `FUN_1400c9810` reads display data with stride `0x54` at container offsets `+0x8c, +0xe0, +0x134, +0x188, +0x1dc, +0x230, +0x284, +0x2d8, +0x32c, +0x380, +0x3d4, +0x428, +0x47c, +0x4d0` (base ID), `+0x90, +0xe4, ...` (alt ID), `+0xa4, +0xf8, ...` (missing-part flag byte). For slot k these map to **record (k+1)** offsets `+0x0c, +0x10, +0x24` respectively. Base/alt IDs ARE saved (record (k+1)+0x0c, +0x10 = T[8+5k+2], T[8+5k+3]). The missing-part flag at record (k+1)+0x24 is **runtime-only**.
- The first saved record (record 0 at +0x2c) acts as a header; FUN_1400c9810 has no slot reading from it.

**Critical structural insight:** The runtime missing-part flag bytes are populated during the RANDOM INIT step (`FUN_1400b5260`/`FUN_140732750`/`FUN_140733100`), which runs BEFORE deserialize. Deserialize only overwrites the 5 saved u32s per record and never touches the flag bytes. This means defect display is determined by the random init, not the saved blob.

**MewSaveFile::Load wraps the load chain in an RNG state save/restore:**
```c
local_188 = TLS+0x178; uStack_180 = TLS+0x180; ... // save 32-byte xoshiro256** state
FUN_1400b5260(param_3);                              // default init (advances RNG)
*(param_3+0xc48) = db_key;                           // store db_key (AFTER default init)
FUN_1409fcc80(save_ctx, "cats", db_key, blob);       // SQLite read by db_key
FUN_14022d360(param_3, blob, 0);                     // deserialize (overwrites saved fields only)
FUN_140734760(param_3+0x60);                         // bone placement
TLS+0x178 = local_188; ...                            // restore RNG state
```

**Open paradox (Direction 45):** Because the RNG save/restore wraps the entire chain, every cat enters `FUN_1400b5260` with the *same* TLS+0x178 state. With no cat-specific input visible to `FUN_1400b5260` (db_key isn't stored until AFTER it returns), every cat would receive identical default body parts and identical default flags — yet cats clearly differ. Resolution candidates:
(i) `FUN_140733100` (the unmapped step inside `FUN_140732750`) reads cat-specific state from somewhere and re-seeds the RNG (or hashes into part selection).
(ii) The save/restore wrapper has a path I missed where it does NOT restore (e.g., on first creation vs reload).
(iii) Ghidra's argument count for `FUN_1400b5260` is wrong — its true signature has 4 args (`int param_3` and `char param_4` are referenced) and the caller passes more than the decompile shows; one of those carries cat-specific state.

**Direction 45 follow-up (2026-04-26):**
- `FUN_140733100` is `glaiel::CatVisuals::reroll_voice(Gender)` — voice pitch randomizer (uses TLS+0x178 RNG, writes voice ID and pitch at param_1 + 0x668 / + 0x688). NOT the missing-part flag setter. Closed.
- The full load chain is: `FUN_1400d5600` (lazy on-demand cache) → alloc 0xc58 → memset(0) → **`FUN_14005dd60(catData)`** (CatData constructor) → `FUN_14022dfb0` (MewSaveFile::Load) → save RNG → `FUN_1400b5260` (default init: FUN_140732750 random parts → FUN_140733100 random voice → FUN_140734760 bone placement) → store db_key → SQLite read → `FUN_14022d360` (deserialize) → `FUN_140734760` (bone placement again) → restore RNG.
- `FUN_14005dfd0` (body-part container constructor, called from `FUN_14005dd60`) writes **byte=1 at container offset CatPart_k + 0x18** for k=0..18 (19 CatParts, stride 0x54 starting from container+0x2c). This is the "default = present" flag init step.
- Cross-check with `FUN_1400c9810`'s flag reads (at container offsets `+0xa4`, `+0xf8`, ..., stride `0x54` starting from `+0xa4`): if CatParts start at container+0x2c, those flag reads land at **CatPart_(k+1) + 0x24** — a DIFFERENT byte from the +0x18 the constructor writes.

**Critical open offset puzzle:** Direction 33 labeled the missing-part flag as `CatPart+0x18` (citing breeding code FUN_1400a5390). The constructor writes to `+0x18` consistent with that. But FUN_1400c9810 reads from `+0x24` of CatPart_(k+1). These cannot both be the same flag unless one of:
(a) Direction 33's `+0x18` label is correct in breeding context but display reads a different field (`+0x24`), in which case the missing-part flag at `+0x24` has no known setter and stays 0 by memset → all cats should show defects.
(b) The slot↔CatPart mapping is different from what I derived (slot k = CatPart k with an internal layout where what I called "+0x24" is actually "+0x18"). Resolution would require a layout audit using a runtime memory snapshot.
(c) FUN_1400a5390 and FUN_1400c9810 actually read DIFFERENT flag bytes (a "breed-time inheritance flag" at +0x18 vs a "display-time missing flag" at +0x24), and the display flag is set elsewhere we haven't traced.

**Next concrete steps (priority order):**

1. **Resolve the +0x18 vs +0x24 puzzle empirically.** Re-decompile FUN_1400a5390 and verify the exact CatPart offset it reads for the missing-part check. Compare to FUN_1400c9810's container offsets. If both functions read the SAME byte (at the same offset within a slot record), then the constructor-set +0x18=1 is the answer and the load-chain question shifts to: "what sets +0x18=0 for cats with defects?" If they read DIFFERENT bytes, then we have two distinct flags and need to find the setter for the display flag.
2. **Audit the slot↔CatPart mapping with a runtime byte dump.** Modify the parser (or write a new investigate_direction46.py) to dump the raw bytes at container offsets `+0x44+k*0x54` (constructor-set) and `+0xa4+k*0x54` (display-read) for Whommie/Bud/Kami/Murisha. If these bytes ARE in the saved blob (which we've documented they are not), they would distinguish defective cats. If not in the blob, this confirms the runtime-only nature.
2. **Verify `FUN_1400b5260`'s true signature and the actual call-site arguments** in `FUN_14022dfb0`. Read the assembly at `1400d5858` (the call to MewSaveFile::Load) and the call from there to `FUN_1400b5260` to see what is actually passed in RDX, R8, R9. Ghidra's "1 arg" rendering may be wrong.
3. **Trace `FUN_1400d5600`'s caller paths to confirm whether the cache check ever bypasses the RNG-restoring path.** If lazy-load order varies between sessions, every cat's defect outcome would also vary — contradicting the observed stability of defects. So either the order is fixed or per-cat reseeding makes order irrelevant.
4. ~~**Row-audit the .sav file's other SQLite tables for per-cat keys**~~ — **CLOSED (Direction 44).** All 5 tables and all 11 files blobs fully row-audited. No per-cat defect data exists anywhere in the save file. The entire on-disk save is exhausted.

**Reference Cats**

- Whommie (`db_key=853`): eye=139, eyebrow=23, parsed defects include Fur Birth Defect; missing parser detections are Eye Birth Defect and Eyebrow Birth Defect.
- Kami (`db_key=840`): clean control; eye=139, eyebrow=23; parent of Whommie with Petronij.
- Bud (`db_key=887`): ear=132; parsed Leg Birth Defect; missing parser detection is Ear Birth Defect.
- Petronij (`db_key=841`) and Murisha (`db_key=852`): parent/control cats used in family comparisons.
- Flekpus (`db_key=68`) and Lucyfer (`db_key=255`): useful examples for explicit parsed defect / equipment edge cases.

`parse_save()` returns `SaveData`; cats have `db_key` and `_uid_int`, not `uid`. Reuse helper patterns from `tools/field_mapper/investigate_direction29.py`, `investigate_direction30.py`, and `investigate_direction31.py`.

**Mapped Cat Blob Corridor**

Current save-side map from `save_parser.py::Cat.__init__` plus Directions 29-31:

- Header: `breed_id:u32 -> uid:u64 -> name:utf16str -> name_tag:str`; `personality_anchor = r.pos` immediately after `name_tag`.
- Parent/collar block: `parent_uid_a:u64 -> parent_uid_b:u64 -> collar:str -> u32`.
- Pre-T block: 64 bytes = 8 x `f64`; not a per-slot array.
- T body-part array: serializer writes 73 u32s; parser historically reads 72. Direction 33 maps this precisely:
  - T[0..2] = top-level body-part fields from `CatData+0x78`, `+0x7c`, `+0x80`.
  - T[3..72] = 14 body-part records of five u32s each.
  - For each body-part record, `T[index+0]` = `CatPart+0x04` visible/base part ID, `T[index+1]` = `CatPart+0x08` texture/fur echo, and `T[index+2..4]` = `CatPart+0x0c..0x14`.
  - The runtime missing-part byte `CatPart+0x18` is not serialized in T.
  The 73rd u32 is the final field of the final body-part slot and is always `0` in observed saves.
- Version >=17 extras: two u32s (`CatData+0x88`, `CatData+0x84`).
- Gender token string, body-size f64, then three 7-u32 stat records:
  `stat_base[7]`, `stat_mod[7]`, `stat_sec[7]`.
- `CatData+0x788` token string (`"none"`/stat/status) plus empty `FUN_14022d100` fixed header in this snapshot.
- Direction 35 maps `FUN_14022d360`'s write order from `+0x788` through equipment exactly:
  - `+0x788` token string, then `FUN_14022d100` list at `+0x7a8` (14 fixed bytes for empty).
  - 10 strings at fixed 0x20 stride: `+0x7d0` (`DefaultMove` anchor), `+0x7f0`, `+0x810`, `+0x830`, `+0x850`, `+0x870`, `+0x890`, `+0x8b0`, `+0x8d0`, `+0x8f0`.
  - 4 `(string, u32)` slots at fixed 0x28 stride: `+0x910/+0x930`, `+0x938/+0x958`, `+0x960/+0x980`, `+0x988/+0x9a8`. This is the `birth_defects` effect-list corridor.
  - 5 equipment slots via `FUN_14022b1f0` at `+0x9b0`, `+0xa10`, `+0xa70`, `+0xad0`, `+0xb30` (stride 0x60).
- The parser's "DefaultMove" run reads 11 strings = 10 pre-corridor strings + corridor slot 0 string. `passive1_tier` is corridor slot 0's u32. The three `(string, u32)` tail slots are corridor slots 1-3. All four corridor slots are read; for Whommie and Bud all four are `"None"`/tier 1.
- Class string at `CatData+0xc10`, then fixed tail (Direction 37): `+0xc30` u32, `+0xc50` f64, `+0xc38` f64 (v>7), `+0xc40` f64 (v>8), variable byte vector via `FUN_1402345e0` at `CatData+0x8` (`u64 size; size*u8`, gate v>0xd), `+0xc34` u32 (v>0xe), `+0xc00` f64 (v>0xf), `+0xc08`/`+0xc09`/`+0xc0a` three u8 (v>0xf), `+0x744..+0x780` 16-u32 array (v>0x11). All read or skipped accurately; none contains hidden defect data for the reference cats.

**Binary Findings**

- `FUN_14022ce10`: body-part container serializer. Writes 73 u32s, not 72. It writes three top-level fields and then calls `FUN_14022cd00` for 14 body-part records.
- `FUN_14022cd00`: per-body-part serializer. Writes five u32s: `CatPart+0x04`, `+0x08`, `+0x0c`, `+0x10`, `+0x14`. It does not serialize `CatPart+0x18`.
- `FUN_1400a6790`: `glaiel::CatData::breed(...)`. This is the executable-side birth-defect generation lead. It calls `FUN_1400c17f0` with `"birth_defects"` and `FUN_1400ca4a0` with `"birth_defect"`.
- `FUN_1400a5390`: body-part inheritance helper. For each body part, it looks up `(part_category, part_id)` from the two parents. If the byte at `CatPart+0x18` is zero, it substitutes part ID `0xFFFFFFFE` for the lookup. It then writes the selected visible/base ID to the child at `CatPart+0x04`. This explains how runtime code can use GON block `-2` without saving a literal `0xFFFFFFFE`.
- `FUN_1400a5600`: paired body-part post-process helper. It randomly copies the selected `CatPart+0x04` visible/base ID between paired parts such as left/right limbs or features.
- `FUN_1400ca4a0`: helper called from `CatData::breed` with `"birth_defect"`. It chooses candidate CatPartIDs and tests whether applying the named tag succeeds.
- `FUN_1400c17f0`: helper called from `CatData::breed` with `"birth_defects"`. It collects/applies a list-like GON/resource entry and then tests the resulting mutation/passive application.
- `FUN_14022cf90`: 7-u32 record serializer. Direction 29 proved the three calls are `stat_base`, `stat_mod`, `stat_sec`, not hidden defect data.
- `FUN_14022d100`: variable-length list serializer. Direction 30 found `count=0` for all 947 parsed cats in the investigation snapshot.
- `FUN_14022b1f0`: equipment slot serializer. Called five times, not four.
- `FUN_140734760`: visual bone/transform placement. Pure render-placement code; not defect detection.

**Ruled-Out Lead Index**

Detailed evidence remains in `tools/field_mapper/*direction*_results.txt` and the scripts named below. Short version:

- T-slot extra fields: `T[index+1]`, `T[index+2]`, `T[index+3]`, `T[index+4]` do not distinguish Whommie/Bud from controls. `T[index+1]` is the fur/texture echo. `T[2]` is variable but not useful as a defect flag.
- Literal ID scans: no aligned `2` or `0xFFFFFFFE` carrier found in Whommie/Bud blobs outside explicit T values. See Directions 1, 7a-7f.
- Simple bitmasks: plausible slot/category masks were tested and failed. See Direction 7d.
- SQLite/file tables: `files`, `properties`, `npc_progress`, and the enumerated schema do not contain per-cat defect data. Pedigree has lineage/COI data, not a direct defect registry. See Directions 7c, 7e, 8, 13b, 16.
- Community save editors: TypeScript and Python editors read/write the same T array or simpler versions of it; no hidden second defect field found. See Directions 19-21.
- Pre-T block: structured as personality/relationship-like f64 values. `f64[2]` stores lover/breeding partner db_key or NaN. No simple threshold separates defect-positive from clean controls. See Directions 15, 17.
- Gender/body-scale/stat area: discarded f64 after gender is body-size-like and not defect-correlated; `FUN_14022cf90` records are stats. See Directions 18, 29.
- Post-stat / ability / equipment corridor: `CatData+0x788`, `FUN_14022d100`, ability tail, three tail slots, equipment, and class string are mapped and not the Whommie/Bud hidden effect carrier. See Directions 26, 30, 31.
- `CatData+0x910..0x9b0` `birth_defects` effect-list corridor: exactly four `(string, u32)` slots, all read by the parser (slot 0 via the `DefaultMove` run + `passive1_tier`, slots 1-3 via the three tail `(string, u32)` pairs). All four slots are `"None"`/tier 1 for Whommie and Bud. Not the carrier. See Direction 35.
- `CatData+0x7d0..+0x8f0` 10 pre-corridor strings: every cat's strings are well-formed identifiers; the parser drops only literal `"None"`/`"DefaultMove"` filler. Whommie/Bud have no unique tokens vs the 947-cat roster. See Direction 36.
- Post-equipment region (Directions 37-39): `FUN_1402345e0` byte vector at `CatData+0x8` is a generic byte-vector serializer; size=0 for all 5 reference cats. The three u8 flags at `+0xc08/+0xc09/+0xc0a` correlate with class/passive counters, not defects. The 16-u32 array at `+0x744..+0x780` is all-zero for all 5 reference cats. The full post-equipment write order is documented in `tools/field_mapper/direction37_results.txt`.
- GPAK GON entries for IDs 139/23/132 (Direction 40): no GON entries exist for these IDs in `eyes.gon` / `eyebrows.gon` / `ears.gon`. They are anonymous base cosmetic shapes. Parser correctly returns None. Lookup is not the bug.
- Saved stat arrays (Direction 41): Whommie/Bud have `stat_mod = [0,0,0,0,0,0,0]`. Defect stat penalties are NOT baked into save-time stat_mod. Class bonuses ARE (Kami's Druid bonuses). Different mechanism for defects.
- `FUN_1401d2ff0` as the per-cat save loader (Direction 43 correction): this function is `GlobalProgressionData::ComputeSaveFilePercentage`, applying progression-milestone mutations from save % vs `next_cat_mutation` SQLite key — not the per-cat defect applier. Direction 42's identification was wrong.
- Direction 33's per-record field labels (Direction 45 refinement): the offsets are correct (FUN_14022cd00 writes 5 u32s at record+0x04..+0x14) but the *labels* "visible/base part ID" for `+0x04` and "texture/fur echo" for `+0x08` were inferred from breeding code (FUN_1400a5390) and may not match the runtime display reads. FUN_1400c9810 reads display IDs at record_(k+1)+0x0c (base) and +0x10 (alt), and the missing-part flag at record_(k+1)+0x24. Of these only +0x0c and +0x10 are saved.
- COI/ancestry correction: raw parsed `cat.inbredness` was the wrong COI source. Cached pedigree COI / `kinship_coi(parent_a, parent_b)` is the validated source. Directions 22-23 are superseded by Directions 24-25.
- External reverse-engineering: SciresM's breeding notes support a separate birth-defect-parts pass after normal part inheritance, but do not specify save serialization. Treat as a runtime-code lead, not proof of a saved parallel array.
- **SQLite full row-audit (Direction 44):** All 5 tables and all 11 `files` blobs have now been row-audited. Schema: `cats` (947 rows, key+blob), `files` (11 rows, key+blob), `furniture` (146 rows, key+blob), `properties` (266 rows, key+value), `winning_teams` (0 rows). Files keys: `house_state`, `house_unlocks`, `inventory_backpack`, `inventory_storage`, `inventory_trash`, `name_gen_history_w`, `npc_progress`, `pedigree`, `save_file_cat`, `tutorial_tokens`, `unlocks`. None contain per-cat defect data. `pedigree` blob is a parallel-hashmap of parent links + COI memos — Whommie/Bud have standard entries with no defect flags. `properties.random_seed` is a 32-byte xoshiro256** state (`ea24843d...`). The entire on-disk save is now exhausted. No per-cat defect field exists anywhere in the file.

---

### tools/field_mapper/

Reverse-engineering pipeline for discovering binary field offsets. Dev-only — not part of the main app.

### Reverse-Engineering Environment Setup

Use the fixed investigation save snapshot unless deliberately testing the live save:

```powershell
$env:INVESTIGATION_SAVE = "C:\Users\Byron\gitprojects\MewgenicsBreedingManager\test-saves\investigation\steamcampaign01_20260424_191107.sav"
```

**Ghidra is accessed via the `mcp__mewgenics-ghidra` MCP server** — do not attempt to run Ghidra headlessly from this project directory. The Ghidra project and binary live in WSL; use MCP tools for all decompilation and symbol work:

- `mcp__mewgenics-ghidra__decompile_function` — decompile a function by address or name
- `mcp__mewgenics-ghidra__search_symbols_by_name` — find functions/globals by name pattern
- `mcp__mewgenics-ghidra__search_strings` — search for string literals in the binary
- `mcp__mewgenics-ghidra__search_code` — search decompiled code
- `mcp__mewgenics-ghidra__list_cross_references` — find callers/callees of an address
- `mcp__mewgenics-ghidra__read_bytes` — read raw bytes at a virtual address
- `mcp__mewgenics-ghidra__gen_callgraph` — generate a call graph around a function
- `mcp__mewgenics-ghidra__list_imports` / `list_exports` — imports/exports table

Java scripts under `tools/` (e.g. `GhidraCf90Probe.java`, `GhidraDefectRefs.java`) are legacy artifacts from the previous headless workflow and do not need to be run. They remain in the repo as reference for the queries they performed.

On 2026-04-25, `rg.exe` returned "Access is denied" in this workspace. If that recurs, use PowerShell `Get-ChildItem ... | Select-String ...` as the fallback search path.

Useful current Python investigation scripts:

- `tools\field_mapper\investigate_direction32.py` searches `Mewgenics.exe` and `resources.gpak` (legacy — prefer reading `game-files/resources/gpak-text/` directly for GON/CSV lookups) for defect strings/constants and maps executable hits to virtual addresses.
- `tools\field_mapper\investigate_direction29.py` confirms `FUN_14022cf90` = stat arrays.
- `tools\field_mapper\investigate_direction30.py` maps `CatData+0x788` + the empty `FUN_14022d100` header.
- `tools\field_mapper\investigate_direction31.py` maps the `DefaultMove` run, three tail slots, equipment block, and class string.
- `tools\field_mapper\investigate_direction33.py` writes the T-index-to-CatPart map and focus-cat slot dumps.
