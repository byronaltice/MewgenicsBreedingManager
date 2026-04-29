# Defect Investigation Notes

Visual Mutation and Birth Defect parsing notes. Confirmed findings; history, ruled-out leads, directions, next steps. Holds only the most important current info. Keep this file updated after each step of the investigation.

Less-important, non-current, obsolete, or incorrect info should be placed in `findings/`. Additional files may be made in `findings/` as needed, current files may be updated. Ensure the below index remains updated.

## Multi-Agent Workflow

Investigation work uses registered subagents — dispatch via the Agent tool rather than working inline. Opus plans and reviews; subagents execute.

| Subagent | `subagent_type` | Use for |
|---|---|---|
| Ghidra decompile/analysis | `defect-ghidra` | Any Ghidra MCP work: decompile, symbol lookup, cross-references, callgraph |
| Save-blob script work | `defect-blob-walker` | Any Python script against save blobs: roster scans, byte-diffs, field extraction |
| gpak text corpus search | `defect-text-resources` | Any search/analysis of `game-files/resources/gpak-text/` |

Briefings, shared rules, and example prompts: `defect-investigation/subagents/`.

Pivotal-claim verification flow: `subagents/_shared/verification_policy.md` (orchestrator) and `subagents/_shared/verification_mode.md` (subagent return shape).

Start investigation sessions with `/advisor-strategy` to enter planning mode.

---

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

**Direction 48 update (2026-04-26):** spec-compliant SWF accumulation does NOT explain the defects. The outer `CatHeadPlacements` MovieClip (`char_id=11007`) places anchors at frame 0 that persist via the SWF display-list. Whommie's frame 304 accumulated anchor set is *identical* to Kami's frame 99 under spec-compliant rules.

**Direction 49 update (2026-04-26):** `FUN_140734760` walks the **outer** clip's children at offset `+0xb0`, not a depth=1 sub-clip — sub-clip-descent hypothesis is closed. Frame is selected by `FUN_140996b80(clip, headShape - 1)`, then a flat name-comparison loop runs. The puzzle now lives inside `FUN_140996b80` and the runtime frame-table format at `plVar18 + 0xd0`: how does Glaiel's SWF runtime build the per-frame child list, and does it diverge from the spec-compliant accumulation Direction 48 simulated?

**Direction 50 update (2026-04-27):** Two findings, one of which is a major correction. (a) `FUN_140996b80`'s SWF runtime builds spec-compliant cumulative per-frame snapshots at `+0xd0[+0xb0]` via `FUN_140997590` — frames 99 (Kami) and 304 (Whommie) produce IDENTICAL anchor child lists, matching Direction 48. The runtime does NOT diverge from spec. (b) **CRITICAL CORRECTION:** `FUN_140734760` does NOT write `CatPart+0x18`. The bytes it sets (CatData offsets 0x290, 0x2e4, 0x3e0, 0x434, 0x488, 0x4dc, 0x530, 0x584) sit at `CatPart+0xC` — exactly 0xC bytes earlier than the +0x18 missing-part flag. Direction 47's review used the right addresses but mislabeled them as +0x18 flags. Consequence: the load-time mechanism that clears `CatPart+0x18` to zero for missing parts is once again UNIDENTIFIED. Placement reconstruction sets a separate "anchor populated" sub-field at +0xC that the display chain (reading +0x18 per Direction 46) does not consult. See `audit/direction/direction50_results.txt`.

**Direction 51 update (2026-04-28):** Cross-reference scan results. (a) **Placement-reconstruction model is closed.** `CatPart+0xC` is written by `FUN_140734760` and read by no one — there is no `+0xC` → `+0x18` bridge. (b) **No zero-writer to `CatPart+0x18` found** across 19 decompiled functions covering all callers of `FUN_14005dfd0`, the load chain, `FUN_140734760`, and the breed path (Low confidence — absence claim, scope-bounded). **Incidental discovery:** `FUN_1400a5390` reads the *parent* cat's +0x18 at breed time and writes `0xFFFFFFFE` to the *child*'s `+0x04` if the parent has the missing-part flag set — but where the child's `+0x04` lands in the on-disk corridor has never been traced. See `audit/direction/direction51_results.txt`.

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

### Direction 48 — Outer CatHeadPlacements clip decoded; outer-clip hypothesis contradicted

`catparts.swf` is uncompressed (FWS, SWF v17). `CatHeadPlacements` is `DefineSprite` `char_id=11007` with 1505 frames; frame N = head shape N (1-indexed). Frame 0 places all 8 anchor objects (`leye, reye, lear, rear, ahead, aneck, aface, mouth`) at fixed depths; subsequent frames update only depth=1 (head clip), depth=2 (tex), depth=27 (scars).

Spec-compliant SWF display-list accumulation:
- Frame 99 (Kami) anchors: `{aface, ahead, aneck, lear, leye, rear, reye}`.
- Frame 304 (Whommie) anchors: **identical to frame 99** — frame 304 explicitly re-places `reye`; `leye` persists from frame 0 via depth-62 has_move update.
- Frame 319 (Bud) anchors: `{aface, ahead, aneck, lear, mouth, rear, reye}` — `lear`+`rear` are present (contradicts ear-defect hypothesis); `leye` is removed (would predict an eye defect Bud doesn't have).

Outer-clip hypothesis is contradicted. Refined hypothesis: `FUN_140734760` walks the depth=1 per-frame child sub-clip (the actual CatHead clip — `char=6534` for head 99, `char=6753` for head 304) recursively for named anchor children. The outer `CatHeadPlacements` clip selects which CatHead sub-clip to render; the missing-anchor signal lives inside each sub-clip, not in the outer display list.

Full decode: `audit/direction/direction48_results.txt`. Reusable parser: `scripts/investigate-direction/investigate_direction48.py`.

### Direction 51 — Cross-reference scan: +0xC is a dead-end, no zero-writer to +0x18 found

(a) `CatPart+0xC` ("anchor populated", written by `FUN_140734760`) is read by **no function** in the binary's analyzed scope. `FUN_1400c9810` reads only the `+0x18` offsets to route to `0xFFFFFFFE`; no other readers found. **The placement-reconstruction model (Direction 47) is closed** — there is no one-step indirection from `+0xC` to the missing-part flag.

(b) **No function writes byte zero to `CatPart+0x18`** across 19 decompiled functions: all callers of `FUN_14005dfd0`, the full load chain (`FUN_14022dfb0`, `FUN_14022cd00`, `FUN_14022fd70`), the breed path (`FUN_1400a6790`, `FUN_1400a5390`, `FUN_1400a5600`), `FUN_1400cb130`, `FUN_1400c1ac0`, `FUN_1400c8570`, and `FUN_140734760` itself. `FUN_14005dfd0` writes byte=1; nobody writes byte=0. **Low confidence absence claim** — scope-bounded; a writer may exist in a callee not yet decompiled, or the defect mechanism may not go through `+0x18` at all.

**Incidental discovery (worth following up):** `FUN_1400a5390` reads the **parent** cat's `+0x18` during breeding and writes `0xFFFFFFFE` to the **child**'s `+0x04` if the parent has the missing-part flag set. The child's `+0x04` per CatPart is a serialized field (`FUN_14022cd00` writes +0x04, +0x08, +0x0C, +0x10, +0x14), but where it lands in the on-disk corridor has never been traced. Direction 41's exhaustive corridor scan looked for `0xFFFFFFFE` only in the T array; the per-CatPart `+0x04` field within the CatParts container at `CatData+0x60` may be a separate place to look.

See `audit/direction/direction51_results.txt`.

### Direction 50 — SWF runtime is spec-compliant; `FUN_140734760` writes CatPart+0xC, not +0x18

Decompiled the full SWF frame-seek path (`FUN_140996b80` → `FUN_140997590` → `FUN_140996020` → `FUN_140997210`) and re-verified `FUN_140734760` against the Direction 46 record layout.

**SWF runtime is spec-compliant.** `+0xd0` points to a frame-table struct holding raw per-frame tag arrays at `+8` plus a lazily-built cumulative per-frame snapshot vector at `+0xb0` (built by `FUN_140997590` on first frame seek). The snapshot for frame N is the full accumulated display-list state through frame N, computed left-to-right with spec-compliant tag merging. Frames 99 and 304 produce identical anchor sets — outer-clip frame selection cannot explain Whommie/Bud defects.

**`FUN_140734760` writes `CatPart+0xC`, not `+0x18` (Direction 47 corrected).** `param_1` is `double*` (8-byte stride). The bytes set at CatData offsets 0x290, 0x2e4, 0x338, 0x38c, 0x3e0, 0x434, 0x488, 0x4dc, 0x530, 0x584 are at sub-offset 0xC from each CatPart record base — exactly 0xC bytes earlier than the Direction 46 `+0x18` flags at 0x29c, 0x2f0, ..., 0x4e8. `FUN_140734760` is therefore writing a separate "anchor populated" sub-field, NOT the missing-part flag the display chain reads.

**Open consequence:** the load-time setter of `CatPart+0x18 = 0` is unidentified again. Either (i) some downstream function reads `CatPart+0xC` and propagates to `+0x18`, or (ii) a different path entirely produces missing parts. See `audit/direction/direction50_results.txt`.

### Direction 49 — `FUN_140734760` walks the outer clip, not a sub-clip

Decompiled `FUN_140734760` and confirmed (2 lines of evidence per claim):

- Resource fetch: `FUN_1409a5bb0(0x73, &"CatHeadPlacements")` returns the outer `char_id=11007` MovieClip handle (`plVar18`).
- Frame seek: `FUN_140996b80(plVar18, head_id - 1)` where `head_id` is `*(int*)(CatData + 0x84)` (saved `headShape`, 1-based).
- Anchor walk: linear pointer iteration over `plVar18 + 0xb0` for `plVar18[0xac]` items (the same small-vector layout used inside `FUN_140996b80`). Each child's name is read from `child + 0x48` and string-compared against `"leye"`, `"reye"`, `"lear"`, `"rear"`, `"mouth"`, `"ahead"`, `"aneck"`, `"aface"` (all confirmed via `read_bytes` at `DAT_1411044b4`, `DAT_1411044bc`, `DAT_141104478`, `DAT_141104480` plus inline literals). No recursion, no descent into the depth=1 sub-clip.

So the depth=1-sub-clip hypothesis from Direction 48 is **closed**. The walk happens on the outer `CatHeadPlacements` clip's children at the seeked frame.

This re-opens a paradox: Direction 48's spec-compliant SWF accumulation gives frames 99 and 304 identical anchor sets, yet Whommie (head 304) has defects Kami (head 99) does not. Resolution must lie in how `FUN_140996b80` populates `plVar18 + 0xb0` from its frame table at `plVar18 + 0xd0` — Glaiel's runtime SWF representation may differ from the on-disk SWF tag stream Direction 48 walked.

---

## Open Questions

1. **Where in the on-disk corridor does each CatPart's `+0x04` (effective part ID) land?** `FUN_14022cd00` (per-part serializer) writes +0x04, +0x08, +0x0C, +0x10, +0x14. `FUN_1400a5390` writes `0xFFFFFFFE` into the child's `+0x04` at breed time when a parent's `+0x18` is zero. If `+0x04` survives serialize/load, Whommie/Bud's CatPart+0x04 should hold `0xFFFFFFFE` on disk. Direction 41's exhaustive scan only checked the T array for `0xFFFFFFFE` — the per-CatPart `+0x04` slot within the CatParts container at `CatData+0x60` was never explicitly checked at that sub-offset.

2. **Is `FUN_1400c9810`'s "+0x18" read actually a Ghidra offset misread?** Direction 46 corrected one offset mistake before. If the real check is on `+0x04` (which holds `0xFFFFFFFE` directly when set by breeding), the `+0x18` flag chain is a red herring.

3. **Who actually clears `CatPart+0x18` to zero?** Direction 51's cross-reference scan found no zero-writer across 19 functions (Low confidence absence claim). Either it lives in an unanalyzed callee or the defect mechanism doesn't go through `+0x18` at all (see Q2).

4. **RNG paradox (Direction 45):** Every cat enters `FUN_1400b5260` with the same TLS state. How do cats get different body parts? One of: (i) undiscovered 4th arg carrying cat-specific state, (ii) a non-restoring branch in the wrapper, (iii) the cache check bypasses the RNG-restoring path for some callers.

---

## Best Path Forward (priority order)

1. **Direction 52 — Trace CatPart+0x04 to its on-disk corridor.** Two complementary tasks. (a) Ghidra: re-read `FUN_14022cd00` (per-part serializer) and identify exactly which save corridor / SQLite column receives each CatPart's `+0x04` field. (b) Blob-walker: once the corridor is mapped, scan Whommie's and Bud's on-disk record at the `+0x04` offset of every CatPart and check for `0xFFFFFFFE`. If found, we've located the defect signal and the parser fix is straightforward.
2. **Verify `FUN_1400c9810`'s `+0x18` access.** Cheap Ghidra task: read the raw assembly at the relevant lines to confirm the byte offset is `0x18` not something Ghidra mis-decoded. Direction 46 caught one offset error; worth confirming this one isn't another.
3. **If +0x04 corridor scan comes up empty** — expand the zero-writer search to all callees of `FUN_14022dfb0`, `FUN_1400c9810`, and `FUN_1400b5260` not yet decompiled.
4. **Prototype parser-side reconstruction.** Once the defect signal source is confirmed, synthesize `0xFFFFFFFE` visual defect entries from saved data.
5. **Resolve the RNG paradox** (lower priority — doesn't block parser fix).

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
