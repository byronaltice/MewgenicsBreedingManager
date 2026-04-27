# Blob Corridor Map

Byte-for-byte map of the per-cat save blob as understood from `save_parser.py::Cat.__init__` plus Directions 29-47.
All fields listed are confirmed serialized (on-disk). Runtime-only fields are marked explicitly.

## Header

- `breed_id : u32`
- `uid : u64`
- `name : utf16str`
- `name_tag : str`
- `personality_anchor = r.pos` immediately after `name_tag`

## Parent / Collar Block

- `parent_uid_a : u64`
- `parent_uid_b : u64`
- `collar : str`
- `u32`

## Pre-T Block

64 bytes = 8 × f64. Not a per-slot array. Structured as personality/relationship-like f64 values. `f64[2]` stores lover/breeding partner db_key or NaN.

## T Body-Part Array (Direction 33)

Serializer writes 73 u32s; parser historically reads 72.

- `T[0..2]` = top-level body-part fields from `CatData+0x78`, `+0x7c`, `+0x80`
- `T[3..72]` = 14 body-part records of five u32s each

Per record: `T[index+0]` = `CatPart+0x04` (visible/base part ID), `T[index+1]` = `CatPart+0x08` (texture/fur echo), `T[index+2..4]` = `CatPart+0x0c..0x14`.

The runtime missing-part byte `CatPart+0x18` is **not serialized** in T. The 73rd u32 is the final field of the final slot and is always 0 in observed saves.

## Version ≥ 17 Extras

Two u32s: `CatData+0x88`, `CatData+0x84`.

## Stat Region

- Gender token string
- Body-size f64
- Three 7-u32 stat records: `stat_base[7]`, `stat_mod[7]`, `stat_sec[7]`

## Ability / Passive Corridor (Directions 30, 31, 35, 36)

- `CatData+0x788` token string (`"none"` / stat / status)
- `FUN_14022d100` list at `+0x7a8` (14 fixed bytes when empty; count=0 for all 947 cats in investigation snapshot)
- 10 strings at fixed 0x20 stride: `+0x7d0` (DefaultMove anchor), `+0x7f0`, `+0x810`, `+0x830`, `+0x850`, `+0x870`, `+0x890`, `+0x8b0`, `+0x8d0`, `+0x8f0`
- 4 `(string, u32)` slots at fixed 0x28 stride: `+0x910/+0x930`, `+0x938/+0x958`, `+0x960/+0x980`, `+0x988/+0x9a8` — this is the `birth_defects` effect-list corridor

The parser's "DefaultMove" run reads 11 strings = 10 pre-corridor strings + corridor slot 0 string. `passive1_tier` = corridor slot 0's u32. Three `(string, u32)` tail slots = corridor slots 1-3. All four slots are `"None"` / tier 1 for Whommie and Bud — **not the carrier**.

## Equipment

5 equipment slots via `FUN_14022b1f0` at `+0x9b0`, `+0xa10`, `+0xa70`, `+0xad0`, `+0xb30` (stride 0x60).

## Post-Equipment Tail (Directions 37-39)

- Class string at `CatData+0xc10`
- `+0xc30` u32
- `+0xc50` f64
- `+0xc38` f64 (v>7)
- `+0xc40` f64 (v>8)
- Variable byte vector via `FUN_1402345e0` at `CatData+0x8` (`u64 size; size*u8`, gate v>0xd) — generic serializer, no defect semantics; size=0 for all 5 reference cats
- `+0xc34` u32 (v>0xe)
- `+0xc00` f64 (v>0xf)
- `+0xc08` / `+0xc09` / `+0xc0a` three u8 (v>0xf) — correlate with class/passive counters, not defects; (0,0,0) for Whommie/Bud/Petronij/Murisha
- `+0x744..+0x780` 16-u32 array (v>0x11) — all zero for all 5 reference cats

## Body-Part Container Layout (Direction 45/46 correction)

Container base = `CatData+0x60`. Serialized records 0..13 at container offsets `+0x2c, +0x80, +0xd4, +0x128, +0x17c, +0x1d0, +0x224, +0x278, +0x2cc, +0x320, +0x374, +0x3c8, +0x41c, +0x470` (stride 0x54).

Each record k: 5 u32s at offsets `+0x04..+0x14` (serialized). Bytes `+0x18..+0x53` are **runtime-only**.

CatData-relative display/breeding bases (used by `FUN_1400c9810` and `FUN_1400a5390`): `+0x8c, +0xe0, +0x134, +0x188, +0x1dc, +0x230, +0x284, +0x2d8, +0x32c, +0x380, +0x3d4, +0x428, +0x47c, +0x4d0`. These equal container-relative record bases + container base (`+0x60`). Offset `+0x18` within each record is the runtime missing-part flag (initialized to 1 by `FUN_14005dfd0`; cleared/set by `FUN_140734760` during bone placement).

## Confirmed Exhausted Regions

The entire on-disk per-cat blob is byte-for-byte mapped. No field distinguishes Whommie/Bud from clean controls. See `findings/ruled_out_leads.md` and `audit/direction/` for full evidence.
