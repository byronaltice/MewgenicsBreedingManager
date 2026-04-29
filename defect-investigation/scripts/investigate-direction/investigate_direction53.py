"""
Direction 53 — Scan CatPart[k]+0x04 on-disk values for 0xFFFFFFFE sentinel.

Hypothesis: Whommie (853) and Bud (887) have 0xFFFFFFFE stored in at least one
CatPart[k]+0x04 field on disk. The runtime display gate (CatPart+0x18) masks this,
so the parser never surfaces it. If confirmed, a trivial parser fix follows:
emit a defect whenever a CatPart's stored +0x04 == 0xFFFFFFFE.

CatPart array serialized layout (from blob_corridor_map.md, Direction 52):
  - T array in blob: 72 u32s starting after header skip block
  - T[0..2]: top-level fields (CatData+0x78, +0x7c, +0x80)
  - T[3..72]: 14 body-part records * 5 u32s each
  - T[3 + k*5 + 0] = CatPart[k]+0x04  (the visible/base part ID, or sentinel)
  - T[3 + k*5 + 1] = CatPart[k]+0x08  (texture echo)
  - T[3 + k*5 + 2] = CatPart[k]+0x0c
  - T[3 + k*5 + 3] = CatPart[k]+0x10
  - T[3 + k*5 + 4] = CatPart[k]+0x14

Runtime-only field CatPart+0x18 is NOT serialized; stride 0x54 but only
the first 5 u32s (+0x04..+0x14) are on-disk.

Task A: locate the T array offset in the decompressed blob for each focus cat.
Task B: scan the 14 CatPart[k]+0x04 values for each focus cat.
Task C: full-roster count of any CatPart[k]+0x04 == 0xFFFFFFFE.
"""
from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

# Script is at: <repo>/defect-investigation/scripts/investigate-direction/
_SCRIPT_DIR  = Path(__file__).resolve().parent
_SCRIPTS_DIR = _SCRIPT_DIR.parent   # defect-investigation/scripts/
_DEFECT_DIR  = _SCRIPTS_DIR.parent  # defect-investigation/
ROOT         = _DEFECT_DIR.parent   # repo root

sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(_SCRIPTS_DIR))  # for common.py

from common import (  # noqa: E402
    BinaryReader,
    decompress_cat_blob,
    iter_cats_from_save,
)

DEFECT_SENTINEL = 0xFFFFFFFE
NUM_CAT_PARTS = 14
T_HEADER_FIELDS = 3      # T[0..2] before the per-part records start
T_FIELDS_PER_PART = 5    # 5 u32s per part record in T
T_TOTAL = T_HEADER_FIELDS + NUM_CAT_PARTS * T_FIELDS_PER_PART  # = 73; parser reads 72

FOCUS: dict[str, int] = {
    "Whommie":  853,
    "Bud":      887,
    "Kami":     840,
    "Petronij": 841,
    "Murisha":  852,
}
DEFECT_POSITIVE = {853, 887}
CLEAN_CONTROLS  = {840, 841, 852}

VISUAL_MUT_NAMES = [
    "Body", "Head", "Tail",
    "Rear Leg (L)", "Rear Leg (R)",
    "Front Leg (L)", "Front Leg (R)",
    "Eye (L)", "Eye (R)",
    "Eyebrow (L)", "Eyebrow (R)",
    "Ear (L)", "Ear (R)",
    "Mouth",
]

# Save file: check INVESTIGATION_SAVE env var, then known locations.
_ENV_SAVE = os.environ.get("INVESTIGATION_SAVE")
if _ENV_SAVE:
    SAVE = Path(_ENV_SAVE)
else:
    _candidates = [
        ROOT / "test-saves" / "investigation" / "steamcampaign01_20260424_191107.sav",
        _DEFECT_DIR / "notes" / "in-game-observations" / "steamcampaign01_20260424_191107.sav",
        _DEFECT_DIR / "game-files" / "saves" / "steamcampaign01_20260424_191107.sav",
    ]
    SAVE = next((p for p in _candidates if p.exists()), _candidates[0])

TOPIC = "part04_disk_scan"
OUT = _DEFECT_DIR / "audit" / "direction" / f"direction53_{TOPIC}_results.txt"

_lines: list[str] = []


def emit(msg: str = "") -> None:
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode())
    _lines.append(msg)


def _find_t_array_offset(raw: bytes) -> tuple[int, str | None]:
    """
    Re-parse the blob header to find the byte offset of the T array.

    Serialization sequence (from blob_corridor_map.md):
      breed_id     : u32        (4 bytes)
      uid          : u64        (8 bytes)
      name         : utf16str   (8 bytes length prefix + char_count*2 bytes)
      name_tag     : str        (8 bytes length prefix + byte_len bytes)
      parent_uid_a : u64        (8 bytes)
      parent_uid_b : u64        (8 bytes)
      collar       : str        (8 bytes length prefix + byte_len bytes)
      reserved     : u32        (4 bytes)
      pre-T skip   : 64 bytes   (8 x f64 personality block)
      --- T array starts here ---

    Returns (offset, error).  error is None on success.
    """
    try:
        r = BinaryReader(raw)
        _breed_id = r.u32()
        _uid = r.u64()
        _name = r.utf16str()
        _name_tag = r.str()
        _parent_a = r.u64()
        _parent_b = r.u64()
        _collar = r.str()
        _reserved = r.u32()
        r.skip(64)
        return r.pos, None
    except Exception as exc:
        return -1, str(exc)


def _read_t_array(raw: bytes, t_offset: int) -> list[int] | None:
    """
    Read T_TOTAL u32s starting at t_offset.
    Returns None if the blob is too short.
    We read all 73 (T_TOTAL) to cover the final +0x14 of the last record.
    """
    needed = t_offset + T_TOTAL * 4
    if needed > len(raw):
        return None
    return [
        struct.unpack_from("<I", raw, t_offset + i * 4)[0]
        for i in range(T_TOTAL)
    ]


def part04_values_from_t(t: list[int]) -> list[int]:
    """
    Extract the 14 CatPart[k]+0x04 values from the T array.
    T[T_HEADER_FIELDS + k*T_FIELDS_PER_PART] for k in 0..13.
    """
    return [t[T_HEADER_FIELDS + k * T_FIELDS_PER_PART] for k in range(NUM_CAT_PARTS)]


def scan_cat(db_key: int, blob: bytes) -> tuple[list[int] | None, int, str | None]:
    """
    Decompress a cat blob and extract 14 CatPart+0x04 values.

    Returns (part04_list, t_blob_offset, error).
    error is None on success.
    """
    try:
        raw = decompress_cat_blob(blob)
    except Exception as exc:
        return None, -1, f"decompress failed: {exc}"

    t_offset, err = _find_t_array_offset(raw)
    if err:
        return None, -1, f"header parse failed: {err}"

    t = _read_t_array(raw, t_offset)
    if t is None:
        return None, t_offset, f"blob too short for T array at blob offset {t_offset}"

    return part04_values_from_t(t), t_offset, None


def main() -> None:
    emit("Direction 53 — CatPart+0x04 on-disk scan for 0xFFFFFFFE sentinel")
    emit(f"Save : {SAVE}")
    emit(f"Out  : {OUT}")
    emit("")

    if not SAVE.exists():
        emit(f"ERROR: Save file not found: {SAVE}")
        emit("Set INVESTIGATION_SAVE env var to the correct path.")
        return

    # --- Task A + B: focus cats ---
    emit("=" * 72)
    emit("TASK A+B — Focus cats: T-array blob offset and CatPart[k]+0x04 values")
    emit("=" * 72)

    focus_blobs: dict[int, bytes] = {}
    for db_key, blob in iter_cats_from_save(str(SAVE)):
        if db_key in set(FOCUS.values()):
            focus_blobs[db_key] = bytes(blob)

    key_to_name = {v: k for k, v in FOCUS.items()}

    for name, db_key in FOCUS.items():
        blob = focus_blobs.get(db_key)
        if blob is None:
            emit(f"\n{name} (db_key={db_key}): NOT FOUND in save")
            continue

        part04_list, t_offset, err = scan_cat(db_key, blob)
        marker = "[DEFECT+]" if db_key in DEFECT_POSITIVE else "[CONTROL]"

        emit(f"\n{name} (db_key={db_key}) {marker}")
        if err:
            emit(f"  ERROR: {err}")
            continue

        raw = decompress_cat_blob(blob)
        emit(f"  Decompressed blob size : {len(raw)} bytes")
        emit(f"  T-array blob offset    : 0x{t_offset:04x} ({t_offset})")
        emit("")
        emit(f"  {'k':>3}  {'Part Name':<16}  {'T-idx':>5}  {'blob_off':>10}  {'value (hex)':>12}  flagged")
        emit(f"  {'-'*3}  {'-'*16}  {'-'*5}  {'-'*10}  {'-'*12}  {'-'*10}")

        has_sentinel = False
        for k in range(NUM_CAT_PARTS):
            t_idx = T_HEADER_FIELDS + k * T_FIELDS_PER_PART
            blob_off = t_offset + t_idx * 4
            val = part04_list[k]
            part_name = VISUAL_MUT_NAMES[k] if k < len(VISUAL_MUT_NAMES) else f"Part{k}"
            flagged = "*** SENTINEL ***" if val == DEFECT_SENTINEL else ""
            if val == DEFECT_SENTINEL:
                has_sentinel = True
            emit(f"  {k:>3}  {part_name:<16}  {t_idx:>5}  0x{blob_off:08x}  0x{val:08x}  {flagged}")

        emit("")
        if has_sentinel:
            emit(f"  >> SENTINEL 0xFFFFFFFE FOUND for {name} — hypothesis SUPPORTED <<")
        else:
            emit(f"  No sentinel found for {name}")

    # --- Task C: full roster scan ---
    emit("")
    emit("=" * 72)
    emit("TASK C — Full roster: count cats with any CatPart[k]+0x04 == 0xFFFFFFFE")
    emit("=" * 72)
    emit("")

    total_cats = 0
    cats_with_sentinel: list[tuple[int, list[int]]] = []  # (db_key, [k indices])
    parse_errors = 0

    for db_key, blob in iter_cats_from_save(str(SAVE)):
        total_cats += 1
        part04_list, _t_off, err = scan_cat(db_key, bytes(blob))
        if err:
            parse_errors += 1
            continue
        sentinel_slots = [k for k, v in enumerate(part04_list) if v == DEFECT_SENTINEL]
        if sentinel_slots:
            cats_with_sentinel.append((db_key, sentinel_slots))

    emit(f"Total cats scanned : {total_cats}")
    emit(f"Parse errors       : {parse_errors}")
    emit(f"Cats with sentinel : {len(cats_with_sentinel)}")
    emit("")

    if cats_with_sentinel:
        emit(f"{'db_key':>8}  {'name':>12}  slots with 0xFFFFFFFE")
        emit(f"{'-'*8}  {'-'*12}  {'-'*50}")
        for db_key, slots in sorted(cats_with_sentinel):
            cat_name = key_to_name.get(db_key, "")
            slot_desc = ", ".join(
                f"k={k} ({VISUAL_MUT_NAMES[k] if k < len(VISUAL_MUT_NAMES) else f'Part{k}'})"
                for k in slots
            )
            emit(f"{db_key:>8}  {cat_name:>12}  {slot_desc}")
    else:
        emit("  (none — no cat has 0xFFFFFFFE in any CatPart[k]+0x04 field)")

    # --- Summary ---
    emit("")
    emit("=" * 72)
    emit("SUMMARY")
    emit("=" * 72)

    sentinel_set = {db_key for db_key, _ in cats_with_sentinel}
    defect_with_sentinel = sentinel_set & DEFECT_POSITIVE
    control_with_sentinel = sentinel_set & CLEAN_CONTROLS
    other_with_sentinel = sentinel_set - DEFECT_POSITIVE - CLEAN_CONTROLS

    emit(f"Defect-positive cats with sentinel : {sorted(defect_with_sentinel)}")
    emit(f"Control cats with sentinel         : {sorted(control_with_sentinel)}")
    emit(f"Other cats with sentinel           : {len(other_with_sentinel)}")
    emit("")

    if defect_with_sentinel == DEFECT_POSITIVE and not control_with_sentinel:
        emit("HYPOTHESIS STRONGLY SUPPORTED:")
        emit("  All defect-positive cats have 0xFFFFFFFE at a CatPart[k]+0x04.")
        emit("  No control cats have it.")
        emit("  Parser fix path confirmed: detect defect via on-disk +0x04 == 0xFFFFFFFE.")
    elif defect_with_sentinel and not control_with_sentinel:
        emit("HYPOTHESIS PARTIALLY SUPPORTED:")
        emit(f"  {len(defect_with_sentinel)}/{len(DEFECT_POSITIVE)} defect cats have sentinel; "
             f"0 controls do.")
    elif not cats_with_sentinel:
        emit("HYPOTHESIS NOT SUPPORTED:")
        emit("  No cats have 0xFFFFFFFE in any CatPart[k]+0x04.")
    else:
        emit("HYPOTHESIS WEAKENED:")
        emit(f"  {len(defect_with_sentinel)} defect cats + {len(control_with_sentinel)} controls + "
             f"{len(other_with_sentinel)} other cats have the sentinel.")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(_lines), encoding="utf-8")
    emit(f"\nResults written to {OUT}")


if __name__ == "__main__":
    main()
