# Parser and GON Reference

Confirmed, stable findings about how the parser reads the save and how GON files define mutations/defects.
These do not change unless the game updates its save format.

## T Array Structure

`Cat.__init__` reads a 72-element u32 array `T` immediately after a 64-byte skip block. (The on-disk serializer actually writes 73 u32s — the final field of the final slot, always 0; the parser historically stops at 72. See `blob_corridor_map.md`.) Each body-part slot is defined by `_VISUAL_MUTATION_FIELDS` with a fixed `table_index` into T. Known field layout per 5-element slot window (slots at indices 3, 8, 13, 18 ... 68):

- `T[index+0]` = mutation_id (the actual mutation or defect in that slot; 0 / 0xFFFFFFFF = empty)
- `T[index+1]` = always equals `T[0]` (the fur/texture ID repeated in every slot — game engine artifact, not a stat)
- `T[index+2]` = 0 in all observed saves
- `T[index+3]` = small non-zero for some slots (role unknown); does NOT encode mutation stat modifiers
- `T[index+4]` = 0 in all observed saves

The fur slot at index 0 has only 3 fields (`T[0]`, `T[1]`, `T[2]`); `T[1]` = small integer breed/body variant ID (e.g., 8 or 31), `T[2]` = highly variable (0xFFFFFFFF mode) — neither encodes birth defect flags (confirmed via Direction 17).

## Mutation Stat Modifiers

Mutation stat modifiers are **NOT** stored in T. They are defined in the GPAK GON files and the CSV strings table, and applied by the game to `stat_mod` at save time. The parser reads mutation stat effects from `_VISUAL_MUT_DATA` (populated from the GPAK) purely for display.

## Defect Detection

`is_defect` is set True when:
- (a) `700 <= mutation_id <= 706` or `mutation_id == 0xFFFFFFFE` (legacy hardcoded range), OR
- (b) the GPAK entry for that mutation has `tag birth_defect` in its GON block.

The GPAK flag is the authoritative source and catches IDs outside the original range (e.g. Blob Legs = 707, No Ears = ears GON ID 2).

## GPAK GON Format for Mutations

Each body-part GON file (e.g. `data/mutations/legs.gon`) contains numbered blocks. Each block may have:
- A `// comment` as the display name
- `tag birth_defect` to mark it as a birth defect
- Inline stat modifiers: `str 1`, `cha -1`, `spd -2`, `speed -4` (alias for spd), etc.
- `desc "MUTATION_CATEGORY_ID_DESC"` pointing to the CSV strings table for text effects
- A `passives { ... }` sub-block listing gameplay passive effects

`_parse_mutation_gon` extracts all of these and returns `{slot_id: (name, combined_stat_desc, is_birth_defect)}`. The combined `stat_desc` always merges GON header stats with the CSV description (e.g. `-1 CHA, 10% dodge chance`). Low-ID blocks (< 300) are parsed only if they have `tag birth_defect`.

The GON definitions for the missing Whommie/Bud effects are block `-2` (`0xFFFFFFFE` as u32): eyes = `blind -1`, eyebrows = `cha -2`, ears = `dex -2`.

## `_VISUAL_MUT_DATA`

Module-level `dict[str, dict[int, tuple[str, str, bool]]]` keyed by GPAK category (e.g. `'legs'`, `'ears'`, `'texture'`). Populated via `set_visual_mut_data()`. Tuple = `(display_name, stat_desc, is_birth_defect)`.

## Known Base-Shape T Values

Most `ear_L` / `ear_R` slot values for cats without ear mutations are < 300 (e.g. 30, 56, 132) and represent cosmetic base ear shapes, not mutations. These are correctly skipped by the parser. Do not confuse them with defect IDs.

GPAK GON entries for IDs 139 (eyes), 23 (eyebrows), and 132 (ears) do **not** exist in `eyes.gon` / `eyebrows.gon` / `ears.gon`. They are anonymous base cosmetic shapes. Parser correctly returns None for them (confirmed Direction 40).
