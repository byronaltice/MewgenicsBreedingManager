"""
Direction 55 — Byte-diff Whommie vs Kami CatPart records to find candidate inputs
that influence the runtime missing-part flag (CatPart+0x18).

Layout (from blob_corridor_map.md):
  T array: 73 u32s after header skip.
  T[0..2]: top-level CatData fields.
  T[3 + k*5 + 0] = CatPart[k]+0x04  (base part ID)
  T[3 + k*5 + 1] = CatPart[k]+0x08  (texture echo)
  T[3 + k*5 + 2] = CatPart[k]+0x0C
  T[3 + k*5 + 3] = CatPart[k]+0x10
  T[3 + k*5 + 4] = CatPart[k]+0x14

Tasks:
  A — Side-by-side diff of Whommie (853) vs Kami (840), all 14 slots, all 5 fields.
  B — Bud (887) vs Petronij (841) and Murisha (852) diffs (ear slot focus).
  C — Population stats for the eye slot (k=7, +0x04=139) across all 947 cats.
"""
from __future__ import annotations

import os
import struct
import sys
from pathlib import Path
from collections import Counter

# Script is at: <repo>/defect-investigation/scripts/investigate-direction/
_SCRIPT_DIR  = Path(__file__).resolve().parent
_SCRIPTS_DIR = _SCRIPT_DIR.parent   # defect-investigation/scripts/
_DEFECT_DIR  = _SCRIPTS_DIR.parent  # defect-investigation/
ROOT         = _DEFECT_DIR.parent   # repo root

sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(_SCRIPTS_DIR))

from common import (  # noqa: E402
    BinaryReader,
    decompress_cat_blob,
    iter_cats_from_save,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NUM_CAT_PARTS     = 14
T_HEADER_FIELDS   = 3      # T[0], T[1], T[2] = CatData+0x78, +0x7c, +0x80
T_FIELDS_PER_PART = 5      # +0x04, +0x08, +0x0C, +0x10, +0x14 per record
T_TOTAL           = T_HEADER_FIELDS + NUM_CAT_PARTS * T_FIELDS_PER_PART  # 73

FIELD_OFFSETS = [0x04, 0x08, 0x0C, 0x10, 0x14]  # CatPart-relative offsets

VISUAL_MUT_NAMES = [
    "Body", "Head", "Tail",
    "Rear Leg (L)", "Rear Leg (R)",
    "Front Leg (L)", "Front Leg (R)",
    "Eye (L)", "Eye (R)",
    "Eyebrow (L)", "Eyebrow (R)",
    "Ear (L)", "Ear (R)",
    "Mouth",
]

FOCUS: dict[str, int] = {
    "Whommie":  853,
    "Bud":      887,
    "Kami":     840,
    "Petronij": 841,
    "Murisha":  852,
}
DEFECT_POSITIVE = {853, 887}
CLEAN_CONTROLS  = {840, 841, 852}

# Known base IDs from Direction 53
EYE_BASE_ID      = 0x8B   # 139 — Whommie and Kami both have this for k=7,8
EYEBROW_BASE_ID  = 0x17   # 23  — Whommie and Kami both have this for k=9,10
EAR_BUD_ID       = 0x84   # 132 — Bud's ear base ID (k=11,12)

# Eye slot indices
EYE_LEFT_K       = 7
EYE_RIGHT_K      = 8
EYEBROW_LEFT_K   = 9
EYEBROW_RIGHT_K  = 10
EAR_LEFT_K       = 11
EAR_RIGHT_K      = 12

# Save path
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

TOPIC = "catpart_diff"
OUT = _DEFECT_DIR / "audit" / "direction" / f"direction55_{TOPIC}_results.txt"

_lines: list[str] = []


def emit(msg: str = "") -> None:
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode())
    _lines.append(msg)


# ---------------------------------------------------------------------------
# Core extraction helpers
# ---------------------------------------------------------------------------

def _find_t_array_offset(raw: bytes) -> tuple[int, str | None]:
    """
    Re-parse blob header to find the T array start offset.
    Sequence: breed_id(u32), uid(u64), name(utf16str), name_tag(str),
              parent_a(u64), parent_b(u64), collar(str), reserved(u32),
              skip(64 bytes) -> T array starts here.
    """
    try:
        r = BinaryReader(raw)
        _breed_id   = r.u32()
        _uid        = r.u64()
        _name       = r.utf16str()
        _name_tag   = r.str()
        _parent_a   = r.u64()
        _parent_b   = r.u64()
        _collar     = r.str()
        _reserved   = r.u32()
        r.skip(64)
        return r.pos, None
    except Exception as exc:
        return -1, str(exc)


def _read_t_array(raw: bytes, t_offset: int) -> list[int] | None:
    """Read T_TOTAL u32s starting at t_offset. Returns None if too short."""
    needed = t_offset + T_TOTAL * 4
    if needed > len(raw):
        return None
    return [
        struct.unpack_from("<I", raw, t_offset + i * 4)[0]
        for i in range(T_TOTAL)
    ]


def extract_catpart_tuples(raw: bytes) -> tuple[list[tuple[int, ...]] | None, str | None]:
    """
    Extract 14 5-tuples of (f04, f08, f0c, f10, f14) from the T array.
    Returns (tuples, error). error is None on success.
    """
    t_offset, err = _find_t_array_offset(raw)
    if err:
        return None, f"header parse failed: {err}"
    t = _read_t_array(raw, t_offset)
    if t is None:
        return None, f"blob too short for T at offset {t_offset}"
    tuples = []
    for k in range(NUM_CAT_PARTS):
        base = T_HEADER_FIELDS + k * T_FIELDS_PER_PART
        tuples.append(tuple(t[base + f] for f in range(T_FIELDS_PER_PART)))
    return tuples, None


def load_focus_cats(save_path: Path) -> dict[int, list[tuple[int, ...]]]:
    """Load and extract CatPart tuples for all focus cats."""
    focus_keys = set(FOCUS.values())
    result: dict[int, list[tuple[int, ...]]] = {}
    for db_key, blob in iter_cats_from_save(str(save_path)):
        if db_key not in focus_keys:
            continue
        try:
            raw = decompress_cat_blob(bytes(blob))
        except Exception as e:
            emit(f"[WARN] db_key={db_key} decompress failed: {e}")
            continue
        tuples, err = extract_catpart_tuples(raw)
        if err:
            emit(f"[WARN] db_key={db_key} extract failed: {err}")
            continue
        result[db_key] = list(tuples)
    return result


# ---------------------------------------------------------------------------
# Diff helpers
# ---------------------------------------------------------------------------

def _diff_mask(ta: tuple[int, ...], tb: tuple[int, ...]) -> list[int]:
    """Return list of field indices where ta[i] != tb[i]."""
    return [i for i in range(len(ta)) if ta[i] != tb[i]]


def _tuple_str(t: tuple[int, ...]) -> str:
    return "  ".join(f"0x{v:08x}" for v in t)


def print_side_by_side_diff(
    cat_a_name: str,
    cat_a_id: int,
    cat_b_name: str,
    cat_b_id: int,
    parts_a: list[tuple[int, ...]],
    parts_b: list[tuple[int, ...]],
    highlight_slots: set[int] | None = None,
) -> list[int]:
    """
    Print a side-by-side diff table. Returns list of slot indices that differ.
    """
    emit(f"  Diff: {cat_a_name} (db_key={cat_a_id}) [DEFECT+]  vs  "
         f"{cat_b_name} (db_key={cat_b_id}) [CONTROL]")
    emit(f"  Fields: +0x04  +0x08  +0x0C  +0x10  +0x14  (each shown as hex u32)")
    emit("")

    hdr = (f"  {'k':>3}  {'Part Name':<16}  "
           f"{'--- ' + cat_a_name + ' ---':^55}  "
           f"{'--- ' + cat_b_name + ' ---':^55}  "
           f"{'Diff fields'}")
    emit(hdr)
    emit("  " + "-" * (len(hdr) - 2))

    differing_slots: list[int] = []
    for k in range(NUM_CAT_PARTS):
        ta = parts_a[k]
        tb = parts_b[k]
        diff = _diff_mask(ta, tb)
        part_name = VISUAL_MUT_NAMES[k] if k < len(VISUAL_MUT_NAMES) else f"Part{k}"
        diff_desc = ""
        if diff:
            differing_slots.append(k)
            changed_fields = ", ".join(f"+0x{FIELD_OFFSETS[i]:02X}" for i in diff)
            diff_desc = f"<<< DIFF: {changed_fields}"

        highlight = highlight_slots and k in highlight_slots
        prefix = "  >>" if highlight else "    "
        emit(
            f"{prefix} {k:>3}  {part_name:<16}  "
            f"{_tuple_str(ta)}    "
            f"{_tuple_str(tb)}    "
            f"{diff_desc}"
        )

    return differing_slots


# ---------------------------------------------------------------------------
# Task A — Whommie vs Kami
# ---------------------------------------------------------------------------

def task_a(focus_data: dict[int, list[tuple[int, ...]]]) -> None:
    emit("=" * 100)
    emit("TASK A — Whommie (853) vs Kami (840): Full 14-slot CatPart 5-tuple diff")
    emit("=" * 100)
    emit("")

    parts_whommie = focus_data.get(853)
    parts_kami    = focus_data.get(840)

    if parts_whommie is None:
        emit("ERROR: Whommie (853) not found in save"); return
    if parts_kami is None:
        emit("ERROR: Kami (840) not found in save"); return

    interesting_slots = {EYE_LEFT_K, EYE_RIGHT_K, EYEBROW_LEFT_K, EYEBROW_RIGHT_K}
    differing_slots = print_side_by_side_diff(
        "Whommie", 853, "Kami", 840,
        parts_whommie, parts_kami,
        highlight_slots=interesting_slots,
    )

    emit("")
    emit(f"  Slots that differ: {differing_slots}")
    if not differing_slots:
        emit("  ALL 14 slots are IDENTICAL between Whommie and Kami.")
    else:
        for k in differing_slots:
            part_name = VISUAL_MUT_NAMES[k] if k < len(VISUAL_MUT_NAMES) else f"Part{k}"
            ta = parts_whommie[k]
            tb = parts_kami[k]
            diff = _diff_mask(ta, tb)
            emit(f"  Slot k={k} ({part_name}):")
            for fi in diff:
                emit(f"    +0x{FIELD_OFFSETS[fi]:02X}: Whommie=0x{ta[fi]:08x}  Kami=0x{tb[fi]:08x}")

    # Explicit check for eye/eyebrow slots
    emit("")
    emit("  --- Eye / Eyebrow slot detail ---")
    for k in sorted(interesting_slots):
        part_name = VISUAL_MUT_NAMES[k]
        ta = parts_whommie[k]
        tb = parts_kami[k]
        diff = _diff_mask(ta, tb)
        diff_desc = "DIFFER" if diff else "identical"
        emit(f"  k={k} ({part_name}): +0x04 Whommie=0x{ta[0]:08x} Kami=0x{tb[0]:08x}  [{diff_desc}]")
        if diff:
            for fi in diff:
                emit(f"    +0x{FIELD_OFFSETS[fi]:02X} changed: Whommie=0x{ta[fi]:08x}  Kami=0x{tb[fi]:08x}")


# ---------------------------------------------------------------------------
# Task B — Bud vs controls
# ---------------------------------------------------------------------------

def task_b(focus_data: dict[int, list[tuple[int, ...]]]) -> None:
    emit("")
    emit("=" * 100)
    emit("TASK B — Bud (887) vs Petronij (841) and Murisha (852): Ear-slot focus")
    emit("=" * 100)

    parts_bud       = focus_data.get(887)
    parts_petronij  = focus_data.get(841)
    parts_murisha   = focus_data.get(852)

    if parts_bud is None:
        emit("ERROR: Bud (887) not found"); return

    interesting_slots = {EAR_LEFT_K, EAR_RIGHT_K}

    # Check Bud ear base ID
    bud_ear_l = parts_bud[EAR_LEFT_K][0]
    bud_ear_r = parts_bud[EAR_RIGHT_K][0]
    emit(f"\n  Bud ear base IDs: k={EAR_LEFT_K} +0x04=0x{bud_ear_l:08x}  k={EAR_RIGHT_K} +0x04=0x{bud_ear_r:08x}")

    for ctrl_name, ctrl_id, ctrl_parts in [
        ("Petronij", 841, parts_petronij),
        ("Murisha",  852, parts_murisha),
    ]:
        emit(f"\n  --- Bud vs {ctrl_name} ---")
        if ctrl_parts is None:
            emit(f"  ERROR: {ctrl_name} ({ctrl_id}) not found"); continue

        ctrl_ear_l = ctrl_parts[EAR_LEFT_K][0]
        ctrl_ear_r = ctrl_parts[EAR_RIGHT_K][0]
        ear_match = "MATCH" if ctrl_ear_l == bud_ear_l else "no match"
        emit(f"  {ctrl_name} ear base IDs: k={EAR_LEFT_K} +0x04=0x{ctrl_ear_l:08x}  [{ear_match}]  "
             f"k={EAR_RIGHT_K} +0x04=0x{ctrl_ear_r:08x}")

        differing_slots = print_side_by_side_diff(
            "Bud", 887, ctrl_name, ctrl_id,
            parts_bud, ctrl_parts,
            highlight_slots=interesting_slots,
        )

        emit(f"\n  Slots that differ vs {ctrl_name}: {differing_slots}")
        if not differing_slots:
            emit(f"  Bud and {ctrl_name} are IDENTICAL across all 14 slots.")
        else:
            emit(f"\n  --- Ear slot detail (Bud vs {ctrl_name}) ---")
            for k in [EAR_LEFT_K, EAR_RIGHT_K]:
                ta = parts_bud[k]
                tb = ctrl_parts[k]
                diff = _diff_mask(ta, tb)
                part_name = VISUAL_MUT_NAMES[k]
                diff_desc = "DIFFER" if diff else "identical"
                emit(f"  k={k} ({part_name}): [{diff_desc}]")
                if diff:
                    for fi in diff:
                        emit(f"    +0x{FIELD_OFFSETS[fi]:02X}: Bud=0x{ta[fi]:08x}  {ctrl_name}=0x{tb[fi]:08x}")


# ---------------------------------------------------------------------------
# Task C — Population survey of eye slot across all 947 cats
# ---------------------------------------------------------------------------

def task_c() -> None:
    emit("")
    emit("=" * 100)
    emit(f"TASK C — Population survey of eye slot (k={EYE_LEFT_K}, +0x04 == 0x{EYE_BASE_ID:02x} = {EYE_BASE_ID})")
    emit(f"         across all cats that carry eye base ID {EYE_BASE_ID} (= 0x8B = 139)")
    emit("=" * 100)
    emit("")

    # For each of the 5 fields, collect values from cats where +0x04 == EYE_BASE_ID
    field_values: list[list[int]] = [[] for _ in range(T_FIELDS_PER_PART)]
    total_cats = 0
    matching_cats = 0
    parse_errors = 0

    # Also collect full tuples for pattern analysis
    tuple_counts: Counter[tuple[int, ...]] = Counter()

    for db_key, blob in iter_cats_from_save(str(SAVE)):
        total_cats += 1
        try:
            raw = decompress_cat_blob(bytes(blob))
        except Exception:
            parse_errors += 1
            continue
        tuples, err = extract_catpart_tuples(raw)
        if err or tuples is None:
            parse_errors += 1
            continue

        # Check eye_left slot (k=7)
        t = tuples[EYE_LEFT_K]
        if t[0] == EYE_BASE_ID:
            matching_cats += 1
            for fi in range(T_FIELDS_PER_PART):
                field_values[fi].append(t[fi])
            tuple_counts[t] += 1

    emit(f"  Total cats scanned: {total_cats}")
    emit(f"  Parse errors: {parse_errors}")
    emit(f"  Cats with eye k={EYE_LEFT_K} +0x04 == 0x{EYE_BASE_ID:02x} (= {EYE_BASE_ID}): {matching_cats}")
    emit("")

    if matching_cats == 0:
        emit("  No cats have this eye base ID in the left eye slot — cannot compute population stats.")
        return

    for fi in range(T_FIELDS_PER_PART):
        vals = field_values[fi]
        distinct = sorted(set(vals))
        emit(f"  Field +0x{FIELD_OFFSETS[fi]:02X}:  min=0x{min(vals):08x}  max=0x{max(vals):08x}  "
             f"distinct_count={len(distinct)}  values={[hex(v) for v in distinct]}")

    emit("")
    emit("  --- Distinct (f04, f08, f0c, f10, f14) tuples and frequency ---")
    emit(f"  {'Count':>6}  {'f04':>12}  {'f08':>12}  {'f0c':>12}  {'f10':>12}  {'f14':>12}")
    emit("  " + "-" * 75)
    for tup, cnt in sorted(tuple_counts.items(), key=lambda x: -x[1]):
        vals_str = "  ".join(f"0x{v:08x}" for v in tup)
        emit(f"  {cnt:>6}  {vals_str}")

    # Extra: highlight Whommie's eye tuple in this population
    emit("")
    emit("  --- Reference cat eye tuples in population context ---")
    ref_cats = [
        ("Whommie",  853, "[DEFECT+]"),
        ("Kami",     840, "[CONTROL]"),
        ("Petronij", 841, "[CONTROL]"),
    ]
    for name, db_key, marker in ref_cats:
        for rdb_key2, blob2 in iter_cats_from_save(str(SAVE)):
            if rdb_key2 != db_key:
                continue
            try:
                raw2 = decompress_cat_blob(bytes(blob2))
                tuples2, _ = extract_catpart_tuples(raw2)
                if tuples2:
                    t2 = tuples2[EYE_LEFT_K]
                    freq = tuple_counts.get(t2, 0)
                    emit(f"  {name} ({marker}) eye k={EYE_LEFT_K} tuple: "
                         f"{tuple(hex(v) for v in t2)}  freq_in_population={freq}")
            except Exception:
                pass
            break


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    emit("Direction 55 — CatPart byte-diff: Whommie vs Kami, Bud vs controls")
    emit(f"Save : {SAVE}")
    emit(f"Out  : {OUT}")
    emit("")

    if not SAVE.exists():
        emit(f"ERROR: Save file not found: {SAVE}")
        emit("Set INVESTIGATION_SAVE env var to the correct path.")
        return

    emit("Loading focus cats...")
    focus_data = load_focus_cats(SAVE)
    found_keys = sorted(focus_data.keys())
    emit(f"Loaded focus cats: {found_keys}")
    emit("")

    task_a(focus_data)
    task_b(focus_data)
    task_c()

    emit("")
    emit("=" * 100)
    emit("END Direction 55")
    emit("=" * 100)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(_lines), encoding="utf-8")
    emit(f"\nResults written to {OUT}")


if __name__ == "__main__":
    main()
