# Binary Function Map

Confirmed function identifications from Ghidra decompilation. Stable unless the game binary updates.
Use `mcp__mewgenics-ghidra__decompile_function` or `search_symbols_by_name` to re-examine any of these.

| Function         | Identified Name / Role                                                                                                   |
|------------------|--------------------------------------------------------------------------------------------------------------------------|
| `FUN_14022ce10`  | Body-part container serializer. Writes 73 u32s (3 top-level + 14 records × 5). Calls `FUN_14022cd00` per record.        |
| `FUN_14022cd00`  | Per-body-part serializer. Writes 5 u32s: `CatPart+0x04`, `+0x08`, `+0x0c`, `+0x10`, `+0x14`. Does NOT serialize `+0x18`. |
| `FUN_14022d360`  | `glaiel::SerializeCatData(CatData&, ByteStream&, bool)` — symmetric serializer. `param_2[0]` is ByteStream mode (0=write, 1/2=read). NO defect-application logic, NO RNG. |
| `FUN_14022dfb0`  | `glaiel::MewSaveFile::Load(__int64, CatData&)` — per-cat roster blob loader. Reads SQLite `cats` table by db_key, deserializes via SerializeCatData, then bone placement. |
| `FUN_140230750`  | `glaiel::MewSaveFile::Load(__int64, SaveFileCat&)` — single-cat save_file_cat loader. SQLite key `"save_file_cat"`. NOT the roster loader. `random_seed` is read here only when initializing a fresh adventure. |
| `FUN_1400d5600`  | `get_cat_by_db_key` — lazy on-demand cat retrieval. Hash-cache lookup → SQLite check → calls `MewSaveFile::Load`. 200+ callers. There is NO eager roster loader. |
| `FUN_1400b5260`  | Cat default initializer. Apparent signature: `(CatData*, unused arg2, int gender_or_mode, char use_save_context_mode)`. Uses TLS+0x178 xoshiro256** RNG. Calls `FUN_140732750` → `FUN_140733100` → `FUN_140734760`. Runs BEFORE deserialize. |
| `FUN_140732750`  | Body-part container randomizer. Loads `data/cat.gen.gon`, picks random IDs for each part category, calls `FUN_140733100` before bone placement. |
| `FUN_140733100`  | `glaiel::CatVisuals::reroll_voice(Gender)` — voice pitch randomizer. Uses TLS+0x178 RNG, writes voice ID/pitch at `param_1+0x668` / `+0x688`. NOT a missing-part flag setter. |
| `FUN_140734760`  | Visual bone/transform placement AND `CatPart+0x18` "part present" flag setter — the missing-defect runtime gate. Fetches `"CatHeadPlacements"` MovieClip via `FUN_1409a5bb0(0x73, "CatHeadPlacements")`, calls `FUN_140996b80(clip, *(int*)(CatData+0x84) - 1)` to seek frame=headShape-1, then flat-iterates `clip+0xb0` for `clip[+0xac]` items reading each child's name from `child+0x48`. At entry zeros `CatPart[k]+0x18` for the head anchor slots, then for each matching anchor name (`"leye"`, `"reye"`, `"lear"`, `"rear"`, `"mouth"`, `"ahead"`, `"aneck"`, `"aface"`) found in the frame's display list, sets the corresponding `CatPart+0x18` to 1. **Eyebrow propagation:** at loop end, `CatPart[9]+0x18 ← CatPart[7]+0x18` (lbrow ← leye) and `CatPart[10]+0x18 ← CatPart[8]+0x18` (rbrow ← reye), so eye and eyebrow defects always appear together. Writes occur at param_1-relative byte offsets 0x290, 0x2e4, 0x338, 0x38c, 0x3e0, 0x434, 0x488, 0x4dc, 0x530, 0x584; `param_1` is `double*` = `CatData+0x60`, so absolute addresses are `CatData+0x2f0..+0x5e4`, exactly the `CatPart[k]+0x18` displacements (e.g. CatPart[7]+0x18 = CatData+0x2f0). Also copies bone transform data into matching CatPart transform fields. **Direction 54 correction:** Direction 50 had labeled these writes as `+0xC` from a misread of the double* stride; correct displacement is `+0x18`. The renderer `FUN_1400c9810` reads `+0x18` and emits `0xFFFFFFFE` defect placeholder when zero — so this function IS the source of the missing-defect signal. Direction 54. |
| `FUN_140996b80`  | SWF MovieClip GotoFrame / display-list rebuild. `param_2 = clamp(frame, 0, count-1)`. On frame change: calls `FUN_140997590` to lazily build cumulative per-frame snapshot at `(*(param_1+0xd0))[+0xb0]`, resets live child list at `param_1+0xb0`, then replays the snapshot's tag records via `FUN_140997210` to repopulate the child list (count `+0xac`). Cumulative spec-compliant accumulation confirmed Direction 50. |
| `FUN_140997590`  | SWF cumulative per-frame snapshot builder, lazy single-init under flag `(*(clip+0xd0))[+0xc8]`. Allocates per-depth temp array sized `depthMax * 0x50`. Iterates frames 0..N-1, merging each frame's tags (types 1, 2, 3, 4; skips 5, 6) into the temp array via `FUN_140996020`, then push_back the current state as snapshot entry into `(*(clip+0xd0))[+0xb0]`. Result: snapshot[N] = full display-list state at frame N, spec-compliant. Direction 50. |
| `FUN_140996020`  | SWF tag-merge into per-depth slot. Type 1/4 (PlaceObject full): unconditional copy of all transform/name fields. Type 2 (PlaceObject2 update): copy only flagged fields per bitfield at src+3. Type 3 (RemoveObject): copies record but actual deletion happens at replay time in `FUN_140997210`. Direction 50. |
| `FUN_140997210`  | SWF tag-record replay. Case `'\x03'` (RemoveObject) removes child from live list at `clip+0xb0`. Other cases place/update children. Called by `FUN_140996b80` during frame seek. Direction 50. |
| `FUN_1409a5bb0`  | Resource-by-name fetch (param_1=0x73 selects MovieClip resource type; returns clip handle). Used by `FUN_140734760` to obtain `CatHeadPlacements`. |
| `FUN_14005dd60`  | `CatData` constructor. Called before `MewSaveFile::Load` during lazy load.                                               |
| `FUN_14005dfd0`  | Body-part container constructor. Writes byte=1 at `CatPart+0x18` for all 19 CatParts (k=0..18, stride 0x54, from container+0x2c). Sets "default = present" flag. |
| `FUN_1400a6790`  | `glaiel::CatData::breed(...)`. Birth-defect generation entry point. Calls `FUN_1400c17f0` with `"birth_defects"` and `FUN_1400ca4a0` with `"birth_defect"`. Calls `FUN_1400a5390` with CatData-relative slot bases. |
| `FUN_1400a5390`  | Body-part inheritance helper. If `CatPart+0x18 == 0`, substitutes part ID `0xFFFFFFFE` for the GON lookup. Writes selected part ID to child `CatPart+0x04`. |
| `FUN_1400a5600`  | Paired body-part post-process helper. Randomly copies selected `CatPart+0x04` visible/base ID between paired parts (e.g. left/right limbs). |
| `FUN_1400c9810`  | Effective mutation/display-list builder. Reads category at `CatPart base+0x00`, part id at `base+0x04`, missing flag at `base+0x18`. Same flag as `FUN_1400a5390`. |
| `FUN_1400ca4a0`  | Birth-defect candidate selector. Called from `CatData::breed` with `"birth_defect"`. Loads tagged candidates from `_DAT_141130700`, filters via lambda, shuffles via seeded RNG, applies via `FUN_1400caa20` → `FUN_1400cb130`. Does NOT write `CatPart+0x18`. |
| `FUN_1400caa20`  | `CatData::MutatePiece(...)::lambda_1`. After finding a tagged mutation entry, calls `FUN_1400cb130`.                     |
| `FUN_1400cb130`  | Part ID writer. Writes selected mutation ID into per-part visible ID fields (same offsets Direction 33 mapped to T). Does NOT write `CatPart+0x18`. |
| `FUN_1400c17f0`  | Called from `CatData::breed` with `"birth_defects"`. Reads strings from the GON value, calls `FUN_1400c1600`.            |
| `FUN_1400c1600`  | Checks the serialized string list at `CatData+0x910..0x9b0`, then calls `FUN_1400c1ac0`.                                |
| `FUN_1400c1ac0`  | Writes selected string and u32 tier/flag into the effect-list and applies linked GON effects (`grant_ability`, `lock_item_slot`). |
| `FUN_1400e38c0`  | Tooltip builder. Calls `FUN_1407b1190` to look up mutation entry for the part ID, checks for `"birth_defect"` tag, uses `BirthDefectTooltip`. |
| `FUN_1407b1190`  | Mutation entry lookup by part ID. With ID `0xFFFFFFFE`, finds GON block -2 (tag `birth_defect`).                        |
| `FUN_1401d2ff0`  | `GlobalProgressionData::ComputeSaveFilePercentage`. Applies progression-milestone mutations from save % vs `next_cat_mutation`. NOT the per-cat defect applier. |
| `FUN_14022cf90`  | 7-u32 record serializer. Direction 29 confirmed: three calls = `stat_base`, `stat_mod`, `stat_sec`.                     |
| `FUN_14022d100`  | Variable-length list serializer. `count=0` for all 947 cats in the investigation snapshot.                               |
| `FUN_14022b1f0`  | Equipment slot serializer. Called 5 times.                                                                               |
| `FUN_1402345e0`  | Generic `{u64 size; size * u8}` byte-vector serializer at `CatData+0x8`. No defect semantics.                           |

## Key Data

- `_DAT_141130700` — `FUN_1400ca4a0(..., param_2=1)` birth-defect candidate table: `(0, 1, 2, 3, 3, 3, 3, 3, 8, 8)`. Maps via `FUN_1400cb130` to body/head/tail/rear legs/front legs only — cannot produce eye/eyebrow/ear defects.
- `TLS+0x178` — xoshiro256** RNG state (32 bytes). Seeded from `properties.random_seed` on fresh adventure init. Saved/restored around each lazy cat load.
