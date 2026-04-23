"""Direction #19 -- TypeScript structured mutation table scan.

Community TypeScript save editor (michael-trinity/mewgenics-savegame-editor)
finds a 296-byte structure in the cat blob using a SCAN algorithm — it is NOT
at a fixed offset. Structure layout:

  HEADER (16 bytes):
    +0  f32  scale      (plausible range 0.05–20.0)
    +4  u32  coat_id    (fur/texture ID, non-zero, ≤ 20000)
    +8  u32  t1         (≤ 500)
    +12 u32  t2         (0xFFFFFFFF or < 5000)

  SLOTS 1-14 (20 bytes each):
    +0  u32  slot_id    (mutation ID for this body-part)
    +4  u32  coat_id_or_0  (coat_id echoed or 0)
    +8  u32  unknown_a
    +12 u32  unknown_b
    +16 u32  unknown_c

This script:
1. Implements the TypeScript scan to find the table in Whommie/Kami/Bud/Flekpus.
2. Dumps the full 20-byte slot content for eye_L, eyebrow_L, ear_L slots.
3. Checks if unknown_a/b/c differ between defective and clean cats.
4. Does a roster-wide scan to see if unknown bytes in those slots correlate
   with birth defects.
"""
from __future__ import annotations

import struct
import sqlite3
import sys
from pathlib import Path
from collections import Counter

import lz4.block

ROOT = Path(__file__).resolve().parents[2]
if not (ROOT / "test-saves").exists():
    ROOT = ROOT.parents[2]
sys.path.insert(0, str(ROOT / "src"))

from save_parser import parse_save, _VISUAL_MUTATION_FIELDS  # noqa: E402

SAVE = ROOT / "test-saves" / "steamcampaign01.sav"
OUT = Path(__file__).parent / "direction19_results.txt"

MUT_TABLE_SIZE = 16 + 14 * 20  # 296 bytes

# Slot order in the structured table (TypeScript uses 1-14):
SLOT_LABELS = [
    "body", "head", "tail",
    "leg_L", "leg_R", "arm_L", "arm_R",
    "eye_L", "eye_R",
    "eyebrow_L", "eyebrow_R",
    "ear_L", "ear_R",
    "mouth",
]

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


def f32_le(data: bytes, offset: int) -> float:
    return struct.unpack_from("<f", data, offset)[0]


def u32_le(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def find_mutation_table(raw: bytes) -> int | None:
    """Implement the TypeScript scan algorithm to find the structured table."""
    best_score = -1
    best_off: int | None = None

    n = len(raw)
    if n < MUT_TABLE_SIZE:
        return None

    for base in range(n - MUT_TABLE_SIZE + 1):
        # Check header plausibility
        scale = f32_le(raw, base)
        if not (0.05 <= scale <= 20.0):
            continue

        coat_id = u32_le(raw, base + 4)
        if coat_id == 0 or coat_id > 20000:
            continue

        t1 = u32_le(raw, base + 8)
        if t1 > 500:
            continue

        t2 = u32_le(raw, base + 12)
        if t2 != 0xFFFFFFFF and t2 >= 5000:
            continue

        # Validate slots: at least 10/14 must have coat_id_or_0 == coat_id or 0
        ok = 0
        for i in range(14):
            slot_off = base + 16 + i * 20
            c = u32_le(raw, slot_off + 4)
            if c == coat_id or c == 0:
                ok += 1

        if ok < 10:
            continue

        score = ok * 1000 + base
        if score > best_score:
            best_score = score
            best_off = base

    return best_off


def parse_mutation_table(raw: bytes, base: int) -> dict:
    """Parse the 296-byte structured table at base."""
    scale = f32_le(raw, base)
    coat_id = u32_le(raw, base + 4)
    t1 = u32_le(raw, base + 8)
    t2 = u32_le(raw, base + 12)

    slots = []
    for i in range(14):
        off = base + 16 + i * 20
        slots.append({
            "label": SLOT_LABELS[i],
            "offset": off,
            "slot_id": u32_le(raw, off),
            "coat_id_or_0": u32_le(raw, off + 4),
            "unk_a": u32_le(raw, off + 8),
            "unk_b": u32_le(raw, off + 12),
            "unk_c": u32_le(raw, off + 16),
        })

    return {
        "base": base,
        "scale": scale,
        "coat_id": coat_id,
        "t1": t1,
        "t2": t2,
        "slots": slots,
    }


def main() -> None:
    out("=" * 70)
    out("Direction #19 -- TypeScript structured mutation table scan")
    out("=" * 70)
    out(f"Save: {SAVE}\n")

    save_data = parse_save(str(SAVE))
    cats = save_data.cats
    key_map = {c.db_key: c for c in cats}
    conn = sqlite3.connect(str(SAVE))

    targets = [
        ("Whommie",  853, "MISSING Eye+Eyebrow defects"),
        ("Bud",      887, "MISSING Ear defect"),
        ("Kami",     840, "CLEAN (Whommie's parent, eye=139 brow=23)"),
        ("Petronij", 841, "CLEAN control"),
        ("Flekpus",   68, "DETECTED Eyebrow defect (brow=0xFFFFFFFE)"),
    ]

    out("=" * 70)
    out("STEP 1 -- Find and dump structured table for target cats")
    out("=" * 70)

    for name, db_key, label in targets:
        cat = key_map.get(db_key)
        if cat is None:
            out(f"  {name}: not in save")
            continue
        raw = raw_blob(conn, db_key)
        base = find_mutation_table(raw)
        if base is None:
            out(f"\n{name} ({label}): TABLE NOT FOUND")
            continue

        tbl = parse_mutation_table(raw, base)
        out(f"\n{name} (db_key={db_key}) — {label}")
        out(f"  Table found at: 0x{base:04x}  (blob size: 0x{len(raw):04x})")
        out(f"  scale={tbl['scale']:.4f}  coat_id={tbl['coat_id']}  "
            f"t1={tbl['t1']}  t2=0x{tbl['t2']:08x}")
        out(f"  detected defects: {cat.defects}")
        out(f"  {'Slot':12s} {'slot_id':>10s} {'coat':>6s} {'unk_a':>10s} {'unk_b':>10s} {'unk_c':>10s}")
        out(f"  {'-'*12} {'-'*10} {'-'*6} {'-'*10} {'-'*10} {'-'*10}")
        for s in tbl["slots"]:
            marker = ""
            if s["label"] in ("eye_L", "eyebrow_L", "ear_L"):
                marker = " <<<"
            out(f"  {s['label']:12s} {s['slot_id']:>10d} {s['coat_id_or_0']:>6d} "
                f"{s['unk_a']:>10d} {s['unk_b']:>10d} {s['unk_c']:>10d}{marker}")

    out("\n" + "=" * 70)
    out("STEP 2 -- Compare eye_L / eyebrow_L / ear_L slot bytes: defective vs clean")
    out("  Specifically: unk_a, unk_b, unk_c for slots containing UNDETECTED defects")
    out("=" * 70)

    interest_slots = {"eye_L", "eyebrow_L", "ear_L"}
    out(f"\n  Target slots: {sorted(interest_slots)}")

    for slot_label in sorted(interest_slots):
        slot_idx = SLOT_LABELS.index(slot_label)
        out(f"\n  --- {slot_label} (table slot index {slot_idx}) ---")

        slot_data: list[tuple[str, int, int, int, int, list[str]]] = []
        # (name, slot_id, unk_a, unk_b, unk_c, defects)
        for name, db_key, label in targets:
            cat = key_map.get(db_key)
            if cat is None:
                continue
            raw = raw_blob(conn, db_key)
            base = find_mutation_table(raw)
            if base is None:
                out(f"    {name}: table not found")
                continue
            tbl = parse_mutation_table(raw, base)
            s = tbl["slots"][slot_idx]
            defects = cat.defects
            out(f"    {name:12s}: slot_id={s['slot_id']:6d}  unk_a={s['unk_a']:10d}  "
                f"unk_b={s['unk_b']:10d}  unk_c={s['unk_c']:10d}  defects={defects[:3]}")

    out("\n" + "=" * 70)
    out("STEP 3 -- Roster-wide: for detected eye/brow/ear defects,")
    out("  do unk_a/unk_b/unk_c differ from clean cats in those slots?")
    out("=" * 70)

    slot_stats: dict[str, dict[str, list]] = {
        label: {"defect_unk_a": [], "clean_unk_a": [],
                "defect_unk_b": [], "clean_unk_b": [],
                "defect_unk_c": [], "clean_unk_c": []}
        for label in interest_slots
    }
    found_count = 0
    miss_count = 0

    for cat in cats:
        try:
            raw = raw_blob(conn, cat.db_key)
            base = find_mutation_table(raw)
            if base is None:
                miss_count += 1
                continue
            found_count += 1
            tbl = parse_mutation_table(raw, base)

            for label in interest_slots:
                idx = SLOT_LABELS.index(label)
                s = tbl["slots"][idx]
                # Is this slot a defect? Check T-array-equivalent slot_id
                is_defect = s["slot_id"] >= 300 or s["slot_id"] == 0xFFFFFFFE
                bucket = slot_stats[label]
                if is_defect:
                    bucket["defect_unk_a"].append(s["unk_a"])
                    bucket["defect_unk_b"].append(s["unk_b"])
                    bucket["defect_unk_c"].append(s["unk_c"])
                else:
                    bucket["clean_unk_a"].append(s["unk_a"])
                    bucket["clean_unk_b"].append(s["unk_b"])
                    bucket["clean_unk_c"].append(s["unk_c"])
        except Exception:
            miss_count += 1

    out(f"  Scanned: {found_count} cats found table, {miss_count} missed\n")

    for label in sorted(interest_slots):
        b = slot_stats[label]
        out(f"  {label}:")
        for field in ("unk_a", "unk_b", "unk_c"):
            defect_vals = b[f"defect_{field}"]
            clean_vals = b[f"clean_{field}"]
            if not defect_vals or not clean_vals:
                continue
            d_counter = Counter(defect_vals).most_common(3)
            c_counter = Counter(clean_vals).most_common(3)
            d_set = set(defect_vals)
            c_set = set(clean_vals)
            unique_to_defect = d_set - c_set
            out(f"    {field}: n_defect={len(defect_vals)} n_clean={len(clean_vals)}")
            out(f"      defect top3={d_counter}")
            out(f"      clean  top3={c_counter}")
            if unique_to_defect:
                out(f"      UNIQUE TO DEFECT: {sorted(unique_to_defect)[:10]}")
        out("")

    out("=" * 70)
    out("STEP 4 -- Whommie vs Kami: full hex dump of eye_L/eyebrow_L/ear_L slots")
    out("=" * 70)
    for name, db_key, _ in [("Whommie", 853, ""), ("Kami", 840, ""), ("Bud", 887, ""), ("Flekpus", 68, "")]:
        cat = key_map.get(db_key)
        if cat is None:
            continue
        raw = raw_blob(conn, db_key)
        base = find_mutation_table(raw)
        if base is None:
            out(f"  {name}: table not found")
            continue
        tbl = parse_mutation_table(raw, base)
        out(f"\n  {name} (db_key={db_key}) defects={cat.defects[:3]}:")
        for label in ("eye_L", "eyebrow_L", "ear_L", "mouth"):
            idx = SLOT_LABELS.index(label)
            s = tbl["slots"][idx]
            off = s["offset"]
            slot_bytes = raw[off:off + 20]
            hex_str = " ".join(f"{b:02x}" for b in slot_bytes)
            out(f"    {label:12s} @0x{off:04x}: {hex_str}")
            out(f"               slot_id={s['slot_id']}  unk_a={s['unk_a']}  "
                f"unk_b={s['unk_b']}  unk_c={s['unk_c']}")

    conn.close()
    OUT.write_text("\n".join(_lines), encoding="utf-8")
    print(f"\n[Results written to {OUT}]")


if __name__ == "__main__":
    main()
