# Defect Investigation Notes

Visual Mutation and Birth Defect parsing notes. Confirmed findings; history, ruled-out leads, directions, next steps. Holds only the most important current info. Keep this file updated after each step of the investigation.

Less-important, non-current, obsolete, or incorrect info should be placed in `findings/`. Additional files may be made in `findings/` as needed, current files may be updated. Ensure the below index remains updated.

**Reference files** (read as needed, not required upfront):
- `findings/parser_and_gon_reference.md` — T array structure, GON format, defect detection logic, `_VISUAL_MUT_DATA`
- `findings/blob_corridor_map.md` — Full byte-for-byte save blob field map
- `findings/binary_function_map.md` — All identified Ghidra function names and roles
- `findings/ruled_out_leads.md` — Every closed lead with direction citations
- `findings/OBSOLETE.md` — Superseded or proven-wrong findings

---

## Unresolved Defects: Current State

Goal: find how the game applies three confirmed birth-defect effects that the parser does not currently detect:

- Whommie: Eye Birth Defect (Blind)
- Whommie: Eyebrow Birth Defect (-2 CHA)
- Bud: Ear Birth Defect (-2 DEX)

Known facts:

- The affected T slots contain normal base-shape IDs: eye=139, eyebrow=23, ear=132.
- Clean cats can share those same IDs. Kami/Romanoba share Whommie's eye/eyebrow IDs without those defects.
- The expected literal defect ID `0xFFFFFFFE` does not appear anywhere in Whommie/Bud cat blobs outside the T array.
- The GON definitions for the missing effects are block `-2` (`0xFFFFFFFE` as u32): eyes = `blind -1`, eyebrows = `cha -2`, ears = `dex -2`.
- Do not assume the rendered body part is visually absent. The confirmed fact is only that the game applies the defect effect while the T slot stores a normal base-shape ID.
- The parser already detects normal explicit birth-defect IDs, including explicit `0xFFFFFFFE`, when they appear in `T[index+0]`.
- **Confirmed by user (2026-04-25):** Defects are STABLE across save reloads. The defect data is fully on disk per-cat.
- The entire on-disk per-cat blob and all SQLite tables are byte-for-byte exhausted. No field distinguishes Whommie/Bud from clean controls. See `findings/ruled_out_leads.md`.

Current working model: missing effects are derived from saved visual/head IDs through post-load `CatHeadPlacements` reconstruction — the first confirmed mechanism that can produce stable runtime missing-part defects without any serialized per-cat flag. Whommie has headShape `304`; clean control Kami has headShape `99` (both share eye 139, eyebrow 23). Bud has headShape `319`, ear 132.

---

## Direction History

### Directions 29–41 (summary)

These directions exhausted the entire on-disk blob and all SQLite tables. See `findings/ruled_out_leads.md` for the full closed-leads list with direction citations.

Key structural findings from this phase (detail in `findings/blob_corridor_map.md`):
- T array is 73 u32s (not 72). Runtime `CatPart+0x18` missing-part flag is NOT serialized.
- `birth_defects` effect-list corridor (`+0x910..+0x9b0`) is fully read; all four slots are `"None"` for Whommie/Bud.
- Defect stat penalties are NOT baked into save-time `stat_mod`. Class bonuses ARE.

### Direction 42 — Runtime display chain mapped

- `FUN_1400c9810` builds the effective-mutations list by reading `CatPart+0x18` (runtime-only "missing part" flag; if 0, effective partID = `0xFFFFFFFE`).
- `FUN_1400e38c0` (tooltip builder) calls `FUN_1407b1190`; with `0xFFFFFFFE` it finds GON block -2 (tag `birth_defect`) and shows `BirthDefectTooltip`. There is NO fallback path — display strictly requires the `0xFFFFFFFE` substitution.

### Direction 43 — Corrected Direction 42 misidentification; found random_seed lead

- `FUN_1401d2ff0` is `GlobalProgressionData::ComputeSaveFilePercentage`, NOT the per-cat save loader. Direction 42's interpretation was wrong.
- `FUN_140230750` (cat save-context loader) reads `"random_seed"` from the SQLite `properties` table and seeds xoshiro256** at `TLS+0x178`. All session-wide `FUN_1400ca4a0` calls use this seeded state.
- `FUN_1400ca4a0` loads `birth_defect`-tagged candidates from `_DAT_141130700`, shuffles via seeded RNG, and applies via `FUN_1400caa20` → `FUN_1400cb130`. Does NOT read any CatData offset directly.

### Direction 44 — save_file_percent path closed; SQLite full row-audit complete

- Investigation save has `save_file_percent=80`, `save_file_next_cat_mutation=90` → the `FUN_1401d2ff0` hook returns early and performs zero `FUN_1400ca4a0` calls.
- `_DAT_141130700` candidate table: `(0, 1, 2, 3, 3, 3, 3, 3, 8, 8)` → maps only to body/head/tail/rear legs/front legs. Cannot produce eye/eyebrow/ear defects.
- All 5 SQLite tables and all 11 `files` blobs fully row-audited. No per-cat defect data anywhere in the save. The entire on-disk save is exhausted.

### Direction 45 — Per-cat load chain mapped end-to-end

Renamed/identified key functions (detail in `findings/binary_function_map.md`):
- `FUN_14022d360` = `glaiel::SerializeCatData` — NO defect application, NO RNG.
- `FUN_14022dfb0` = `glaiel::MewSaveFile::Load(__int64, CatData&)` — per-cat roster blob loader.
- `FUN_1400d5600` = `get_cat_by_db_key` — lazy on-demand. NO eager roster loader.
- `FUN_1400b5260` = cat default initializer. Runs BEFORE deserialize, inside RNG save/restore.
- `FUN_140733100` = `glaiel::CatVisuals::reroll_voice(Gender)`. NOT a missing-part setter. **Closed.**

Full load chain: `FUN_1400d5600` → alloc 0xc58 → memset(0) → `FUN_14005dd60` (CatData constructor) → `FUN_14022dfb0` (MewSaveFile::Load) → save RNG → `FUN_1400b5260` (random parts → random voice → bone placement) → store db_key → SQLite read → `FUN_14022d360` (deserialize) → `FUN_140734760` (bone placement again) → restore RNG.

`FUN_14005dfd0` (body-part container constructor) writes **byte=1 at `CatPart+0x18`** for all 19 CatParts — the "default = present" init step.

**Open paradox:** Because the RNG save/restore wraps the entire chain, every cat enters `FUN_1400b5260` with the *same* TLS+0x178 state and db_key isn't stored until AFTER it returns — yet cats clearly differ. Resolution candidates:
- (i) `FUN_1400b5260`'s true 4-arg signature passes cat-specific state not visible in the decompile.
- (ii) The save/restore wrapper has a path that doesn't restore (first creation vs reload).

### Direction 46 — Offset puzzle resolved; confirmed flag bytes

`FUN_1400a5390` and `FUN_1400c9810` both read the same missing-part flag byte at `CatPart+0x18`. The earlier apparent `+0x24` came from comparing container-relative serializer offsets to CatData-relative display offsets without adding the CatParts container base (`CatData+0x60`). See `audit/direction/direction46_results.txt`.

`FUN_14005dfd0` initializes runtime display/breeding slot `CatPart+0x18` bytes to `1` (present) at CatData offsets `+0xa4, +0xf8, +0x14c, +0x1a0, +0x1f4, +0x248, +0x29c, +0x2f0, +0x344, +0x398, +0x3ec, +0x440, +0x494, +0x4e8`.

`FUN_14022dfb0`'s call to `FUN_1400b5260` passes `R8D=3`, `R9D=0`. Load-time default init appears to run with `param_4=0`, unlike breed-time init from `FUN_1400a6790` with `param_4=1`.

### Direction 47 — Post-load placement reconstruction is the first confirmed missing-flag setter

`FUN_140734760` is not placement-only. It loads `"CatHeadPlacements"` using the current head/placement ID, **clears** facial/attached present flags, and sets specific `CatPart+0x18` flags back to `1` only when the selected placement entry contains matching anchors:

- `"leye"` / `"reye"` set left/right eye present flags.
- Eyebrow records are copied from the eye records at loop end — missing eyes can also produce missing eyebrows.
- `"lear"` / `"rear"` set left/right ear present flags.
- `"mouth"`, `"ahead"`, `"aneck"`, `"aface"` set other placement-driven part flags.

This gives the first confirmed post-load mechanism that can produce **stable runtime missing-part defects without any serialized per-cat flag**.

The placement table is NOT plain GON text. The strings `"CatHeadPlacements"`, `"leye"`, `"reye"`, `"lear"`, `"rear"`, `"mouth"`, `"ahead"`, `"aneck"`, `"aface"` were found in `game-files/resources/gpak-video/swfs/catparts.swf`. See `audit/direction/direction47_b5260_mode_flags_report.txt` and `audit/direction/direction47_review_results.txt`.

**Updated working model after Direction 47:** The unresolved defects are derived from saved visual/head IDs through post-load CatHeadPlacements reconstruction. The parser can probably reproduce them by decoding enough of `catparts.swf` to know which head placement entries omit eye/eyebrow/ear anchors, then adding synthetic `0xFFFFFFFE` defect entries for the affected slots.

---

## Open Questions

1. **Which headShape entries omit eye/eyebrow/ear anchors in `catparts.swf`?** Head 304 (Whommie) lacks eye/eyebrow anchors; head 99 (Kami) has them. Head 319 (Bud) likely lacks ear anchors — needs confirmation from the SWF placement table.

2. **RNG paradox (Direction 45):** Every cat enters `FUN_1400b5260` with the same TLS state. How do cats get different body parts? One of: (i) undiscovered 4th arg carrying cat-specific state, (ii) a non-restoring branch in the wrapper, (iii) the cache check bypasses the RNG-restoring path for some callers.

---

## Best Path Forward (priority order)

1. **Decode CatHeadPlacements from `catparts.swf`.** Extract anchor names for headShape `304`, `99`, and `319`. Confirm that 304 omits `"leye"`/`"reye"`/eyebrows and 319 omits `"lear"`/`"rear"`.
2. **Prototype parser-side reconstruction.** Once anchor omissions are confirmed, synthesize `0xFFFFFFFE` visual defect entries from saved headShape/placement data — no new save-field scan needed.
3. **Resolve the RNG paradox** (lower priority — doesn't block parser fix). Trace `FUN_1400d5600`'s caller paths to check whether lazy-load order is fixed or per-cat reseeding makes it irrelevant.

---

## Reference Cats

- **Whommie** (`db_key=853`): eye=139, eyebrow=23, headShape=304. Parsed defects include Fur Birth Defect; missing: Eye Birth Defect (Blind) and Eyebrow Birth Defect (-2 CHA).
- **Kami** (`db_key=840`): clean control; eye=139, eyebrow=23, headShape=99. Parent of Whommie with Petronij.
- **Bud** (`db_key=887`): ear=132, headShape=319. Parsed: Leg Birth Defect. Missing: Ear Birth Defect (-2 DEX).
- **Petronij** (`db_key=841`) and **Murisha** (`db_key=852`): parent/control cats used in family comparisons.
- **Flekpus** (`db_key=68`) and **Lucyfer** (`db_key=255`): useful examples for explicit parsed defect / equipment edge cases.

`parse_save()` returns `SaveData`; cats have `db_key` and `_uid_int`, not `uid`. Reuse helper patterns from `scripts/investigate-direction/investigate_direction29.py`, `investigate_direction30.py`, and `investigate_direction31.py`.

---

## Reverse-Engineering Environment Setup

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

On 2026-04-25, `rg.exe` returned "Access is denied" in this workspace. If that recurs, use PowerShell `Get-ChildItem ... | Select-String ...` as the fallback.

Useful current Python investigation scripts (see `scripts/investigate-direction/` for direction-specific scripts):

- `scripts/investigate-direction/investigate_direction32.py` — searches `Mewgenics.exe` and maps executable hits to virtual addresses (prefer reading `game-files/resources/gpak-text/` directly for GON/CSV lookups)
- `scripts/investigate-direction/investigate_direction29.py` — confirms `FUN_14022cf90` = stat arrays
- `scripts/investigate-direction/investigate_direction30.py` — maps `CatData+0x788` + empty `FUN_14022d100` header
- `scripts/investigate-direction/investigate_direction31.py` — maps DefaultMove run, three tail slots, equipment block, class string
- `scripts/investigate-direction/investigate_direction33.py` — writes T-index-to-CatPart map and focus-cat slot dumps
