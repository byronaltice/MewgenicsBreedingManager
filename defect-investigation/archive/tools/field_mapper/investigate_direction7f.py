"""Direction 7f -- Is T[2] (and other "unused" slot fields) the defect signal?

Observation from 7a: Whommie T[2]=0xFFFFFFFF, Bud T[2]=0xFFFFFFFF, Kami T[2]=0x41.
CLAUDE.md claims T[+2] is constant 0 -- that appears false. Test across cohort:
does T[2] correlate with defect presence roster-wide?

Also check T[index+2] and T[index+3] for each slot to see if they encode
per-slot defect flags.
"""
from __future__ import annotations

import sys
import struct
import sqlite3
from pathlib import Path
from collections import Counter

import lz4.block

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
_TS = ROOT / "test-saves"
if not _TS.exists():
    _TS = Path(os.path.expandvars(r"%USERPROFILE%\gitprojects\MewgenicsBreedingManager\test-saves"))
SAVE = _TS / "steamcampaign01.sav"
GPAK = _TS / "resources.gpak"
OUT  = Path(__file__).parent / "direction7f_results.txt"

_lines: list[str] = []


def out(msg: str = "") -> None:
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode())
    _lines.append(msg)


def raw_blob(conn, db_key: int) -> bytes:
    row = conn.execute("SELECT data FROM cats WHERE key=?", (db_key,)).fetchone()
    data = bytes(row[0])
    uncomp = struct.unpack_from("<I", data, 0)[0]
    return lz4.block.decompress(data[4:], uncompressed_size=uncomp)


def locate_t_start(raw: bytes, cat) -> int:
    fur  = cat.body_parts["texture"]
    body = cat.body_parts["bodyShape"]
    head = cat.body_parts["headShape"]
    target = struct.pack("<I", fur)
    for i in range(0, len(raw) - 9 * 4):
        if raw[i:i + 4] == target:
            if struct.unpack_from("<I", raw, i + 3 * 4)[0] == body and \
               struct.unpack_from("<I", raw, i + 8 * 4)[0] == head:
                return i
    return -1


def main() -> None:
    from save_parser import parse_save, GameData, set_visual_mut_data
    from save_parser import _VISUAL_MUTATION_FIELDS

    out("=" * 70)
    out("Direction 7f -- T[2] and T[index+2..4] defect correlation")
    out("=" * 70)

    gd = GameData.from_gpak(str(GPAK))
    set_visual_mut_data(gd.visual_mutation_data)
    save_data = parse_save(str(SAVE))
    conn = sqlite3.connect(str(SAVE))

    # ---- STEP 1: T[2] value across full cohort, split by defect presence ----
    out("\nSTEP 1 -- T[2] value roster-wide vs defect presence")
    out("-" * 70)
    t2_defect: Counter = Counter()
    t2_clean: Counter = Counter()
    processed = 0
    defect_cats_t2_ff = []
    defect_cats_t2_other = []
    clean_cats_t2_ff = []
    for cat in save_data.cats:
        try:
            raw = raw_blob(conn, cat.db_key)
            t_start = locate_t_start(raw, cat)
            if t_start < 0:
                continue
            t2 = struct.unpack_from("<I", raw, t_start + 2 * 4)[0]
            processed += 1
            if cat.defects:
                t2_defect[t2] += 1
                if t2 == 0xFFFFFFFF:
                    defect_cats_t2_ff.append(cat.name)
                else:
                    defect_cats_t2_other.append((cat.name, t2, cat.defects))
            else:
                t2_clean[t2] += 1
                if t2 == 0xFFFFFFFF:
                    clean_cats_t2_ff.append(cat.name)
        except Exception:
            pass

    out(f"  Processed {processed} cats")
    out(f"  Defective cats: {sum(t2_defect.values())}  "
        f"Clean cats: {sum(t2_clean.values())}")
    out(f"  T[2] distribution for DEFECTIVE cats (top 10): "
        f"{t2_defect.most_common(10)}")
    out(f"  T[2] distribution for CLEAN cats (top 10): "
        f"{t2_clean.most_common(10)}")
    out(f"  Defective cats with T[2]=0xFFFFFFFF: {len(defect_cats_t2_ff)}")
    out(f"  Defective cats with T[2]!=0xFFFFFFFF (counter-examples): "
        f"{len(defect_cats_t2_other)}")
    for n, v, d in defect_cats_t2_other[:10]:
        out(f"    {n}: T[2]=0x{v:08x}  defects={d}")
    out(f"  Clean cats with T[2]=0xFFFFFFFF (false positives): "
        f"{len(clean_cats_t2_ff)}")
    for n in clean_cats_t2_ff[:10]:
        out(f"    {n}")

    # ---- STEP 2: per-slot T[index+2] across slots with/without defects ----
    out("\nSTEP 2 -- For each slot, T[index+2] values by defect-on-that-slot")
    out("-" * 70)
    # For each body part, look at the T[index+2] value and whether that
    # part has a parsed defect.
    # slot_id of parsed defect is inferable from cat.defects (strings like
    # "Eye Birth Defect") or more precisely from cat.visual_mutations if
    # that's where per-part defect lives.

    # We'll use cat.defects (list of descriptive strings) and check for
    # keyword match per slot.
    slot_keywords = {
        "fur":      ["Fur"],
        "body":     ["Body"],
        "head":     ["Head"],
        "tail":     ["Tail"],
        "leg_L":    ["Leg", "Legs"],
        "leg_R":    ["Leg", "Legs"],
        "arm_L":    ["Arm", "Arms"],
        "arm_R":    ["Arm", "Arms"],
        "eye_L":    ["Eye"],
        "eye_R":    ["Eye"],
        "eyebrow_L":["Eyebrow"],
        "eyebrow_R":["Eyebrow"],
        "ear_L":    ["Ear"],
        "ear_R":    ["Ear"],
        "mouth":    ["Mouth"],
    }

    # Collect T[index+2] and T[index+3] for each slot
    per_slot_data: dict[str, list[tuple[bool, int, int]]] = {
        f[0]: [] for f in _VISUAL_MUTATION_FIELDS
    }
    for cat in save_data.cats:
        try:
            raw = raw_blob(conn, cat.db_key)
            t_start = locate_t_start(raw, cat)
            if t_start < 0:
                continue
            for slot_name, table_idx, *_ in _VISUAL_MUTATION_FIELDS:
                if slot_name == "fur":
                    # fur only has 3 fields
                    continue
                v2 = struct.unpack_from("<I", raw, t_start + (table_idx + 2) * 4)[0]
                v3 = struct.unpack_from("<I", raw, t_start + (table_idx + 3) * 4)[0]
                keywords = slot_keywords.get(slot_name, [])
                has_defect = any(any(k in d for k in keywords)
                                 for d in cat.defects)
                per_slot_data[slot_name].append((has_defect, v2, v3))
        except Exception:
            pass

    for slot_name, data in per_slot_data.items():
        if not data:
            continue
        defect_entries = [(v2, v3) for hd, v2, v3 in data if hd]
        clean_entries  = [(v2, v3) for hd, v2, v3 in data if not hd]
        if not defect_entries:
            continue
        c2_d = Counter(v2 for v2, _ in defect_entries)
        c3_d = Counter(v3 for _, v3 in defect_entries)
        c2_c = Counter(v2 for v2, _ in clean_entries)
        c3_c = Counter(v3 for _, v3 in clean_entries)
        out(f"  {slot_name}: defect_n={len(defect_entries)}  "
            f"clean_n={len(clean_entries)}")
        out(f"    T[+2] defect: {c2_d.most_common(3)}  "
            f"clean: {c2_c.most_common(3)}")
        out(f"    T[+3] defect: {c3_d.most_common(3)}  "
            f"clean: {c3_c.most_common(3)}")

    conn.close()
    OUT.write_text("\n".join(_lines), encoding="utf-8", errors="replace")
    print(f"\n[Results written to {OUT}]")


if __name__ == "__main__":
    main()
