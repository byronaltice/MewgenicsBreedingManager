# Ruled-Out Lead Index

All leads listed here are closed. Do not re-investigate these. Detailed evidence is in `audit/direction/direction##_results.txt` and the corresponding scripts.

- **T-slot extra fields** (`T[index+1..4]`): do not distinguish Whommie/Bud from controls. `T[index+1]` is the fur/texture echo. `T[2]` is variable but not a defect flag. Directions 1, 7a-7f.
- **Literal ID scans**: no aligned `2` or `0xFFFFFFFE` carrier in Whommie/Bud blobs outside explicit T values. Directions 1, 7a-7f.
- **Simple bitmasks**: plausible slot/category masks tested and failed. Direction 7d.
- **SQLite / file tables**: `files`, `properties`, `npc_progress`, and enumerated schema do not contain per-cat defect data. `pedigree` is a parallel-hashmap of parent links + COI memos — Whommie/Bud have standard entries with no defect flags. Directions 7c, 7e, 8, 13b, 16.
- **SQLite full row-audit (Direction 44)**: all 5 tables and all 11 `files` blobs row-audited. Schema: `cats` (947 rows), `files` (11 rows: `house_state`, `house_unlocks`, `inventory_backpack`, `inventory_storage`, `inventory_trash`, `name_gen_history_w`, `npc_progress`, `pedigree`, `save_file_cat`, `tutorial_tokens`, `unlocks`), `furniture` (146 rows), `properties` (266 rows), `winning_teams` (0 rows). None contain per-cat defect data. The entire on-disk save is exhausted.
- **Community save editors**: TypeScript and Python editors read/write the same T array or simpler versions; no hidden second defect field found. Directions 19-21.
- **Pre-T block**: structured as personality/relationship f64 values. No simple threshold separates defect-positive from clean controls. Directions 15, 17.
- **Gender / body-scale / stat area**: discarded f64 after gender is body-size-like, not defect-correlated. `FUN_14022cf90` records are stats. Directions 18, 29.
- **Post-stat / ability / equipment corridor**: `CatData+0x788`, `FUN_14022d100`, ability tail, three tail slots, equipment, and class string are mapped and not the carrier. Directions 26, 30, 31.
- **`CatData+0x910..0x9b0` `birth_defects` effect-list corridor**: exactly four `(string, u32)` slots, all read by the parser. All four are `"None"` / tier 1 for Whommie and Bud. Direction 35.
- **`CatData+0x7d0..+0x8f0` 10 pre-corridor strings**: every cat's strings are well-formed identifiers. Whommie/Bud have no unique tokens vs the 947-cat roster. Direction 36.
- **Post-equipment region**: `FUN_1402345e0` byte vector is a generic byte-vector serializer; size=0 for all 5 reference cats. Three u8 flags correlate with class/passive counters, not defects. 16-u32 array is all-zero for all 5 reference cats. Directions 37-39.
- **GPAK GON entries for IDs 139 / 23 / 132**: no GON entries exist for these IDs in `eyes.gon` / `eyebrows.gon` / `ears.gon`. Anonymous base cosmetic shapes; parser correctly returns None. Direction 40.
- **Saved stat arrays**: Whommie/Bud have `stat_mod = [0,0,0,0,0,0,0]`. Defect stat penalties are NOT baked into save-time `stat_mod`. Class bonuses ARE. Direction 41.
- **`FUN_1401d2ff0` as per-cat save loader**: this is `GlobalProgressionData::ComputeSaveFilePercentage`. Investigation save has `save_file_percent=80`, `save_file_next_cat_mutation=90` — path is gated off entirely. Even when active, its candidate table only covers body/head/tail/rear legs/front legs, not eyes/eyebrows/ears. Directions 43, 44.
- **`random_seed` as per-session defect source**: confirmed by user (2026-04-25) that defects are stable across save reloads, ruling out purely runtime-derived hypotheses.
- **`FUN_140733100` as missing-part setter**: identified as `CatVisuals::reroll_voice(Gender)`. Direction 45 follow-up.
- **`FUN_140734760` as placement-only**: Direction 47 corrected — it also clears/sets `CatPart+0x18` present flags based on `CatHeadPlacements` anchor names. This is the first confirmed missing-flag setter; it is NOT ruled out — see main `DEFECT_INVESTIGATION.md`.
- **COI/ancestry source**: raw parsed `cat.inbredness` was wrong. Cached pedigree COI / `kinship_coi(parent_a, parent_b)` is validated. Directions 22-25.
- **Direction 33's `+0x18` vs `+0x24` offset puzzle**: resolved in Direction 46. Both `FUN_1400a5390` and `FUN_1400c9810` read `CatPart+0x18`; the earlier `+0x24` interpretation used the wrong record bases.
